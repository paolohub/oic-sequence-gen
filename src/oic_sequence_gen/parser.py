"""
parser.py — IARParser: extract and parse an OIC .iar archive into a
sequence-step list that generators can consume.

All integration-specific data (participants, route conditions) is derived
dynamically from the archive contents rather than from hardcoded lookup tables.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from oic_sequence_gen.constants import NS_DEF, NS_FLOW

# ── XML tag helpers ────────────────────────────────────────────────────────────

def _t(local: str, ns: str = NS_FLOW) -> str:
    """Return a Clark-notation tag string: {namespace}local."""
    return f"{{{ns}}}{local}"


def _td(local: str) -> str:
    """Return a Clark-notation tag in the project/definition default namespace."""
    return f"{{{NS_DEF}}}{local}"


def _local(tag: str) -> str:
    """Strip the namespace prefix from a Clark-notation tag."""
    return tag.split("}")[-1] if "}" in tag else tag


# ── IARParser ──────────────────────────────────────────────────────────────────

class IARParser:
    """
    Parses an already-extracted OIC .iar archive directory and produces an
    ordered list of *sequence steps* describing the integration flow.

    Each step is a plain dict with a ``type`` key and format-specific fields.
    Generators consume this list without knowing anything about the XML source.

    Attributes
    ----------
    project_code / project_name / project_version : str
        Integration metadata.
    participants : list of (alias, kind, label)
        Ordered list of diagram participants, built dynamically from the
        connections actually used in the flow.  Always starts with
        ("Client", "actor", "Client") and ("OIC", "participant", "OIC Integration").
    sequence : list of dict
        Ordered sequence steps (see step-type docs below).

    Step types
    ----------
    invoke       : call from one participant to another (+ optional return)
    internal     : OIC-internal operation (assignment, transformer, logger, wait)
    throw        : fault / exception thrown to caller
    response     : successful reply to the trigger (200 OK)
    loop_start   : beginning of a for/while loop block
    loop_end     : end of a loop block
    alt_branch   : start of an alt/else branch (kw='alt' or 'else')
    alt_end      : end of an alt block
    group_start  : start of a named group block (e.g. try, scope, catch)
    group_end    : end of a group block
    par_start    : start of a parallel block (first branch label)
    par_branch   : subsequent parallel branch label
    par_end      : end of a parallel block
    section      : == section divider == (PlantUML only)
    note         : note-over box

    Trigger patterns
    ----------------
    receive        : REST/SOAP trigger (external client → OIC)
    scheduleReceive: OIC Scheduler trigger (no external client)
    pick           : multi-operation trigger (one alt branch per pickReceive)
    """

    def __init__(self, work_dir: str) -> None:
        self.work_dir = Path(work_dir)

        # Populated by parse()
        self.project_code:    str = ""
        self.project_name:    str = ""
        self.project_version: str = ""
        self.applications:    dict[str, dict] = {}
        self.processors:      dict[str, dict] = {}
        self.participants:    list[tuple[str, str, str]] = []
        self.sequence:        list[dict] = []

        # Internal state
        self._add_mt_im:       bool            = False
        self._trigger_binding: str             = "rest"  # binding of the receive/trigger application
        self._conn_info:       dict[str, dict] = {}      # conn_code -> {adapter_type, display_name}
        self._seen_conns:      dict[str, str]  = {}      # conn_code -> alias (dedup)
        self._resources_dir:   Path | None     = None

    # ── Public API ─────────────────────────────────────────────────────────────

    def parse(self) -> None:
        """Parse the extracted archive and populate ``self.sequence``."""
        proj_xml = self._find_project_xml()
        self._resources_dir = proj_xml.parent.parent / "resources"

        # Load connection metadata from appinstances/*.xml
        self._load_conn_info(proj_xml)

        # Participants always start with the two fixed endpoints
        self.participants = [
            ("Client", "actor",       "Client"),
            ("OIC",    "participant", "OIC Integration"),
        ]
        self._seen_conns = {}

        tree = ET.parse(proj_xml)
        root = tree.getroot()

        # Project metadata (elements live in the default xmlns NS_DEF)
        self.project_code    = (root.findtext(_td("projectCode"))    or "").strip()
        self.project_name    = (root.findtext(_td("projectName"))    or "").strip()
        self.project_version = (root.findtext(_td("projectVersion")) or "").strip()

        # Find <icsflow>
        flow: ET.Element | None = None
        for child in root:
            if _local(child.tag) == "icsflow":
                flow = child
                break
        if flow is None:
            raise ValueError("Cannot find <icsflow> in project.xml")

        # Parse declarations
        for app in flow.findall(_t("application")):
            self._parse_application(app)
        for proc in flow.findall(_t("processor")):
            self._parse_processor(proc)

        # Parse the orchestration flow tree
        orch = flow.find(_t("orchestration"))
        if orch is None:
            raise ValueError("Cannot find <orchestration> in project.xml")

        self._add_mt_im = orch.find(_t("integrationMetadata")) is not None

        gt = orch.find(_t("globalTry"))
        if gt is not None:
            # Pattern A (older IARs): entire flow wrapped in <globalTry>/<catchAll>
            global_catch: ET.Element | None = None
            for sub in gt:
                tag = _local(sub.tag)
                if tag == "catchAll":
                    global_catch = sub
                else:
                    self._handle_node(tag, sub)

            if global_catch is not None:
                ca_ref  = global_catch.get("refUri", "")
                ca_name = self._proc_name(ca_ref) if ca_ref else "global_catch"
                self.sequence.append({"type": "section", "title": f"Global CatchAll ({ca_name})"})
                self.sequence.append({
                    "type": "note",
                    "text": "Global CatchAll — any unhandled exception\nehStop: integration stopped",
                })
                self._traverse(global_catch)
        else:
            # Pattern B (newer IARs): flow activities are direct children of <orchestration>
            _meta_tags = {"integrationMetadata", "globalVariable", "trackingVariableGroup"}
            for sub in orch:
                tag = _local(sub.tag)
                if tag not in _meta_tags:
                    self._handle_node(tag, sub)

    # ── Connection info loader ──────────────────────────────────────────────────

    def _load_conn_info(self, proj_xml: Path) -> None:
        """
        Read appinstances/*.xml to build conn_code -> {adapter_type, display_name}.
        Uses plain string matching to avoid namespace complexity in appinstance XML.
        """
        appinstances_dir = proj_xml.parent.parent.parent.parent / "appinstances"
        if not appinstances_dir.is_dir():
            return
        for xml_file in appinstances_dir.glob("*.xml"):
            try:
                text = xml_file.read_text(encoding="utf-8", errors="ignore")
                code  = re.search(r"<instanceCode>([^<]+)</instanceCode>",       text)
                atype = re.search(r"<applicationTypeRef>([^<]+)</applicationTypeRef>", text)
                dname = re.search(r"<displayName>([^<]+)</displayName>",         text)
                if code:
                    self._conn_info[code.group(1).strip()] = {
                        "adapter_type": atype.group(1).strip() if atype else "",
                        "display_name": dname.group(1).strip() if dname else code.group(1).strip(),
                    }
            except Exception:
                pass

    # ── Declaration parsers ────────────────────────────────────────────────────

    def _find_project_xml(self) -> Path:
        for p in self.work_dir.rglob("project.xml"):
            if "PROJECT-INF" in str(p):
                return p
        raise FileNotFoundError("project.xml not found in extracted archive")

    def _parse_application(self, app: ET.Element) -> None:
        name    = app.get("name", "")
        role_el = app.find(_t("role"))
        adapter = app.find(_t("adapter"))
        inbound = app.find(_t("inbound"))

        role    = (role_el.text or "").strip() if role_el is not None else "target"
        code    = ""
        op_name = ""
        if adapter is not None:
            code    = (adapter.findtext(_t("code")) or "").strip()
            op_name = (adapter.findtext(_t("name")) or "").strip()

        binding   = ""
        operation = ""
        if inbound is not None:
            binding   = (inbound.findtext(_t("binding"))   or "").strip()
            operation = (inbound.findtext(_t("operation")) or "").strip()

        if role == "source" and binding:
            self._trigger_binding = binding.lower()

        self.applications[name] = {
            "role": role, "adapter_code": code,
            "op_name": op_name, "binding": binding, "operation": operation,
        }

    def _parse_processor(self, proc: ET.Element) -> None:
        name      = proc.get("name", "")
        proc_type = (proc.findtext(_t("type"))          or "").strip()
        proc_name = (proc.findtext(_t("processorName")) or "").strip()
        self.processors[name] = {"type": proc_type, "pname": proc_name}

    # ── Lookup helpers ─────────────────────────────────────────────────────────

    def _proc_name(self, ref_uri: str) -> str:
        """Return the human-readable name for a processor refUri."""
        proc_id = ref_uri.split("/")[0]
        p = self.processors.get(proc_id, {})
        return p.get("pname") or p.get("type") or proc_id

    def _app_info(self, ref_uri: str) -> dict:
        return self.applications.get(ref_uri.split("/")[0], {})

    def _participant_for(self, app_name: str) -> str:
        """Map an application name to its diagram participant alias."""
        app  = self.applications.get(app_name, {})
        role = app.get("role", "")
        if role == "source":
            return "OIC"
        code = app.get("adapter_code", "")
        return self._get_or_create_participant(code)

    def _get_or_create_participant(self, conn_code: str) -> str:
        """
        Return the diagram alias for *conn_code*, registering a new participant
        in ``self.participants`` on first encounter.
        """
        if conn_code in self._seen_conns:
            return self._seen_conns[conn_code]

        info         = self._conn_info.get(conn_code, {})
        adapter_type = info.get("adapter_type", "")
        display_name = info.get("display_name", conn_code)

        # Derive alias from the adapter technology type (OIC platform identifier).
        # Fall back to sanitized connection code when adapter_type is unavailable.
        base_alias = (
            re.sub(r"[^A-Za-z0-9_]", "", adapter_type).upper()
            if adapter_type
            else self._sanitize_alias(conn_code)
        ) or self._sanitize_alias(conn_code)

        # Label comes from the connection's displayName in appinstances XML.
        label = display_name
        kind  = "participant"

        # Ensure the alias is unique
        existing = {p[0] for p in self.participants}
        alias    = base_alias
        counter  = 2
        while alias in existing:
            alias = f"{base_alias}_{counter}"
            counter += 1

        self.participants.append((alias, kind, label))
        self._seen_conns[conn_code] = alias
        return alias

    @staticmethod
    def _sanitize_alias(code: str) -> str:
        """Create a valid PlantUML/Mermaid identifier from an arbitrary string."""
        return re.sub(r"[^A-Za-z0-9_]", "_", code)[:20].strip("_") or "Part"

    def _route_condition(self, route_ref_uri: str) -> str | None:
        """
        Read the condition label from the expr.properties file that OIC stores
        for each router output.

        Priority:
          1. ExpressionName  (human-readable name set in the mapper)
          2. TextExpression  (the simplified XPath expression, truncated)
          3. None            (caller falls back to the route id attribute)
        """
        if not self._resources_dir:
            return None
        parts = route_ref_uri.split("/")
        if len(parts) < 2:
            return None
        proc_id, output_id = parts[0], parts[1]
        search_dir = self._resources_dir / proc_id / output_id
        if not search_dir.is_dir():
            return None
        for props_file in search_dir.rglob("expr.properties"):
            expr_name = ""
            text_expr = ""
            for line in props_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.startswith("ExpressionName"):
                    _, _, val = line.partition(":")
                    expr_name = val.strip()
                elif line.startswith("TextExpression"):
                    _, _, val = line.partition(":")
                    text_expr = val.strip()
            if expr_name:
                return expr_name
            if text_expr and text_expr.lower() != "else":
                return text_expr[:80] + ("…" if len(text_expr) > 80 else "")
        return None

    # ── Orchestration tree traversal ───────────────────────────────────────────

    def _traverse(self, element: ET.Element) -> None:
        """Dispatch each direct child of *element* to ``_handle_node``."""
        for child in element:
            self._handle_node(_local(child.tag), child)

    def _handle_node(self, tag: str, el: ET.Element) -> None:  # noqa: C901
        ref  = el.get("refUri", "")
        name = el.get("name",   "")
        nid  = el.get("id",     "")

        # ── Trigger / receive ──────────────────────────────────────────────────
        if tag == "receive":
            app     = self._app_info(ref)
            binding = (app.get("binding") or "rest").upper()
            op      = app.get("op_name", "")
            msg     = f"{binding} {op}" if op else f"{binding} trigger"
            self.sequence.append({
                "type": "invoke", "from": "Client", "to": "OIC",
                "msg": msg, "ret": "", "is_trigger": True,
            })
            if self._add_mt_im:
                self.sequence.append({
                    "type": "internal", "actor": "OIC",
                    "msg": "MessageTracker + IntegrationMetadata",
                })
                self._add_mt_im = False

        # ── Scheduled trigger ─────────────────────────────────────────────────
        elif tag == "scheduleReceive":
            if not any(p[0] == "Scheduler" for p in self.participants):
                self.participants.insert(1, ("Scheduler", "actor", "OIC Scheduler"))
            self.sequence.append({
                "type": "invoke", "from": "Scheduler", "to": "OIC",
                "msg": "Scheduled trigger", "ret": "", "is_trigger": True,
            })
            if self._add_mt_im:
                self.sequence.append({
                    "type": "internal", "actor": "OIC",
                    "msg": "MessageTracker + IntegrationMetadata",
                })
                self._add_mt_im = False

        # ── Pick (multi-event trigger) ─────────────────────────────────────────
        elif tag == "pick":
            receives = el.findall(_t("pickReceive"))
            for i, pr in enumerate(receives):
                app = self._app_info(pr.get("refUri", ""))
                op  = app.get("op_name", pr.get("id", f"event {i + 1}"))
                kw  = "alt" if i == 0 else "else"
                self.sequence.append({"type": "alt_branch", "kw": kw, "cond": op or f"event {i + 1}"})
                self.sequence.append({
                    "type": "invoke", "from": "Client", "to": "OIC",
                    "msg": op or f"event {i + 1}", "ret": "", "is_trigger": True,
                })
                self._traverse(pr)
            if receives:
                self.sequence.append({"type": "alt_end"})

        # ── Transformer ───────────────────────────────────────────────────────
        elif tag == "transformer":
            pname = self._proc_name(ref)
            if pname and pname not in ("transformer", ""):
                self.sequence.append({
                    "type": "internal", "actor": "OIC",
                    "msg": f"Transformer — {pname}",
                })

        # ── External invoke ───────────────────────────────────────────────────
        elif tag == "invoke":
            app_name  = ref.split("/")[0]
            app       = self._app_info(ref)
            target    = self._participant_for(app_name)
            op        = app.get("op_name", name)
            operation = app.get("operation", "")
            msg       = f"{op} ({operation})" if operation and operation != op else op
            self.sequence.append({
                "type": "invoke", "from": "OIC", "to": target, "msg": msg, "ret": "",
            })

        # ── Stage File ────────────────────────────────────────────────────────
        elif tag == "stageFile":
            if not any(p[0] == "StageFile" for p in self.participants):
                self.participants.append(("StageFile", "participant", "Stage File (OIC)"))
            pname = self._proc_name(ref)
            self.sequence.append({
                "type": "invoke", "from": "OIC", "to": "StageFile", "msg": pname, "ret": "",
            })

        # ── Wait ──────────────────────────────────────────────────────────────
        elif tag == "wait":
            pname = self._proc_name(ref)
            self.sequence.append({
                "type": "internal", "actor": "OIC", "msg": f"WAIT ({pname or 'wait'})",
            })

        # ── Activity Stream Logger ─────────────────────────────────────────────
        elif tag == "activityStreamLogger":
            pname = self._proc_name(ref)
            self.sequence.append({
                "type": "internal", "actor": "OIC",
                "msg": f"ActivityStreamLogger ({pname})",
            })

        # ── Assignment (standalone) ───────────────────────────────────────────
        elif tag == "assignment":
            pname = self._proc_name(ref)
            self.sequence.append({
                "type": "internal", "actor": "OIC", "msg": f"ASSIGN {pname or name}",
            })

        # ── Label (named group of assignments) ────────────────────────────────
        elif tag == "label":
            self.sequence.append({
                "type": "internal", "actor": "OIC", "msg": f"ASSIGN {name}",
            })
            # Do not recurse — individual assignments are not diagram-worthy

        # ── Throw ─────────────────────────────────────────────────────────────
        elif tag == "throw":
            pname = self._proc_name(ref)
            self.sequence.append({
                "type": "throw", "from": "OIC", "to": "Client", "msg": pname or name,
            })

        # ── For / While loops ─────────────────────────────────────────────────
        elif tag in ("for", "while"):
            pname = self._proc_name(ref)
            self.sequence.append({"type": "loop_start", "label": pname or nid})
            self._traverse(el)
            self.sequence.append({"type": "loop_end"})

        # ── Content-based router ──────────────────────────────────────────────
        elif tag == "router":
            routes = el.findall(_t("route"))
            if not routes:
                return
            if len(routes) == 1:
                cond = self._route_condition(routes[0].get("refUri", ""))
                if cond:
                    self.sequence.append({"type": "alt_branch", "kw": "alt", "cond": cond})
                    self._traverse(routes[0])
                    self.sequence.append({"type": "alt_end"})
                else:
                    # Transparent pass-through: single branch with no readable condition
                    self._traverse(routes[0])
            else:
                for i, route in enumerate(routes):
                    cond = (
                        self._route_condition(route.get("refUri", ""))
                        or route.get("id", f"branch {i + 1}")
                    )
                    kw = "alt" if i == 0 else "else"
                    self.sequence.append({"type": "alt_branch", "kw": kw, "cond": cond})
                    self._traverse(route)
                self.sequence.append({"type": "alt_end"})

        # ── Try block ─────────────────────────────────────────────────────────
        elif tag == "try":
            self.sequence.append({"type": "group_start", "label": f"try: {name}"})
            catch_handlers: list[ET.Element] = []
            for sub in el:
                sub_tag = _local(sub.tag)
                if sub_tag in ("catchAll", "catch"):
                    catch_handlers.append(sub)
                else:
                    self._handle_node(sub_tag, sub)
            self.sequence.append({"type": "group_end"})
            for i, handler in enumerate(catch_handlers):
                htag    = _local(handler.tag)
                ca_name = self._proc_name(handler.get("refUri", ""))
                label   = f"CatchAll: {ca_name}" if htag == "catchAll" else f"Catch: {ca_name}"
                kw      = "alt" if i == 0 else "else"
                self.sequence.append({"type": "alt_branch", "kw": kw, "cond": label})
                self._traverse(handler)
            if catch_handlers:
                self.sequence.append({"type": "alt_end"})

        # ── Scope (named activity group) ──────────────────────────────────────
        elif tag == "scope":
            self.sequence.append({"type": "group_start", "label": f"scope: {name}"})
            self._traverse(el)
            self.sequence.append({"type": "group_end"})

        # ── Parallel execution ────────────────────────────────────────────────
        elif tag == "parallel":
            branches = el.findall(_t("branch"))
            if not branches:
                self._traverse(el)
            else:
                for i, branch in enumerate(branches):
                    bname = branch.get("name", f"branch {i + 1}")
                    step_type = "par_start" if i == 0 else "par_branch"
                    self.sequence.append({"type": step_type, "label": bname})
                    self._traverse(branch)
                self.sequence.append({"type": "par_end"})

        # ── Reply (async response back to caller) ─────────────────────────────
        elif tag == "reply":
            app = self._app_info(ref)
            op  = app.get("op_name", name)
            self.sequence.append({
                "type": "response", "from": "OIC", "to": "Client",
                "msg": op or "reply",
            })

        # ── Stitch (integration-to-integration call) ──────────────────────────
        elif tag == "stitch":
            pname = self._proc_name(ref)
            self.sequence.append({
                "type": "internal", "actor": "OIC", "msg": f"STITCH {pname or name}",
            })

        # ── Notification ──────────────────────────────────────────────────────
        elif tag == "notification":
            pname = self._proc_name(ref)
            self.sequence.append({
                "type": "internal", "actor": "OIC",
                "msg": f"Notification ({pname or name})",
            })

        # ── Designer note / annotation ────────────────────────────────────────
        elif tag == "note":
            text = el.get("description", "") or el.get("name", "")
            if text:
                self.sequence.append({"type": "note", "text": text})

        # ── Stop (successful response) ────────────────────────────────────────
        elif tag == "stop":
            msg = "200 OK" if self._trigger_binding == "rest" else "success"
            self.sequence.append({
                "type": "response", "from": "OIC", "to": "Client", "msg": msg,
            })

        # ── ehStop (error handler stop) ───────────────────────────────────────
        elif tag == "ehStop":
            self.sequence.append({
                "type": "throw", "from": "OIC", "to": "Client",
                "msg": "Generic error (ehStop)",
            })

        # route, catch, catchAll, pickReceive, branch handled by their parent nodes;
        # metadata tags (globalVariable, trackingVariable, …) silently ignored

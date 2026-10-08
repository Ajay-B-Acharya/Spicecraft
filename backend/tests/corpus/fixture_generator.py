"""Conservative source extraction and connected, deterministic scale fixtures."""
from __future__ import annotations

import ast
import copy

SIZES = (10, 25, 50, 100, 250, 500)


def scale_circuit(size, family):
    """Size is the exact component count, not section count."""
    if size not in SIZES or family not in ("resistor", "filter"):
        raise ValueError("Use resistor/filter and one of the six corpus sizes")
    components, wires = [], []
    if family == "resistor":
        for index in range(1, size + 1):
            components.append({"reference": f"R{index}", "type": "resistor", "value": "1k"})
            wires.append({"from": f"R{index}.1", "to": "VIN" if index == 1 else f"R{index-1}.2"})
        wires.append({"from": f"R{size}.2", "to": "GND"})
        sections = size
    else:
        sections = size // 2
        for index in range(1, sections + 1):
            components.extend([{"reference": f"R{index}", "type": "resistor", "value": "1k"},
                               {"reference": f"C{index}", "type": "capacitor", "value": "100n"}])
            wires.extend([{"from": f"R{index}.1", "to": "VIN" if index == 1 else f"R{index-1}.2"},
                          {"from": f"R{index}.2", "to": f"C{index}.1"},
                          {"from": f"C{index}.2", "to": "GND"}])
        if size % 2:
            components.append({"reference": "RLOAD", "type": "resistor", "value": "10k"})
            wires.extend([{"from": "RLOAD.1", "to": f"R{sections}.2"},
                          {"from": "RLOAD.2", "to": "GND"}])
        wires.append({"from": f"R{sections}.2", "to": "VOUT"})
    return {"name": f"Repeated {family} sections ({size} components)",
            "description": f"Deterministic connected {family} network; {sections} sections; no simulation source inserted.",
            "components": components, "wires": wires}


class Unresolved(ValueError):
    pass


def python_definitions(text, fixtures=None):
    """Evaluate only data expressions, never import or execute repository tests.

    Unresolved constructors remain inventory evidence. Assertions, I/O, native
    verification and production pipeline calls are not executed by collection.
    """
    tree = ast.parse(text)
    fixtures = fixtures or {}
    found, unresolved = [], []
    helpers = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
               and node.name in {"component", "circuit", "placed_resistors", "detour_fixture"}}
    consumers = {"build_connectivity", "generate_asc", "generate_asc_with_routing",
                 "generate_asc_with_diagnostics"}

    def assign(target, value, env):
        if isinstance(target, ast.Name):
            env[target.id] = value
        elif isinstance(target, (ast.List, ast.Tuple)):
            for key, item in zip(target.elts, value):
                assign(key, item, env)
        elif isinstance(target, ast.Subscript):
            evaluate(target.value, env)[evaluate(target.slice, env)] = value

    def evaluate(node, env, depth=0):
        if node is None or depth > 15:
            raise Unresolved("Missing expression or expression depth limit")
        ev = lambda value: evaluate(value, env, depth + 1)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id not in env:
                raise Unresolved(f"Dynamic name: {node.id}")
            return env[node.id]
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            return [ev(item) for item in node.elts]
        if isinstance(node, ast.Dict):
            result = {}
            for key, value in zip(node.keys, node.values):
                if key is None:
                    result.update(ev(value))
                else:
                    result[ev(key)] = ev(value)
            return result
        if isinstance(node, ast.Subscript):
            return ev(node.value)[ev(node.slice)]
        if isinstance(node, ast.IfExp):
            return ev(node.body if ev(node.test) else node.orelse)
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            left, right = ev(node.left), ev(node.comparators[0])
            op = node.ops[0]
            if isinstance(op, ast.IsNot):
                return left is not right
            if isinstance(op, ast.Is):
                return left is right
            if isinstance(op, ast.Eq):
                return left == right
            if isinstance(op, ast.NotEq):
                return left != right
        if isinstance(node, ast.JoinedStr):
            return "".join(str(ev(item.value)) if isinstance(item, ast.FormattedValue) else item.value for item in node.values)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -ev(node.operand)
        if isinstance(node, ast.BinOp):
            left, right = ev(node.left), ev(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Mult):
                return left * right
        if isinstance(node, ast.ListComp) and len(node.generators) == 1:
            gen = node.generators[0]
            result = []
            for value in ev(gen.iter):
                local = dict(env)
                assign(gen.target, value, local)
                if all(evaluate(test, local) for test in gen.ifs):
                    result.append(evaluate(node.elt, local))
            return result
        if isinstance(node, ast.Call):
            name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ""
            if name in {"load_circuit", "load_fixture", "_load_circuit"} and node.args:
                filename = ev(node.args[0])
                if filename in fixtures:
                    return copy.deepcopy(fixtures[filename])
            if name == "deepcopy" and node.args:
                return copy.deepcopy(ev(node.args[0]))
            if isinstance(node.func, ast.Attribute) and name in {"items", "keys", "values", "copy", "get"}:
                owner = ev(node.func.value)
                if isinstance(owner, dict):
                    return getattr(owner, name)(*[ev(arg) for arg in node.args])
            if name in {"range", "enumerate", "str", "list"}:
                fn = {"range": range, "enumerate": enumerate, "str": str, "list": list}[name]
                value = fn(*[ev(arg) for arg in node.args])
                if name == "range" and len(value) > 1000:
                    raise Unresolved("Range limit")
                return list(value) if name in {"range", "enumerate"} else value
            if name in helpers:
                helper = helpers[name]
                local = dict(env)
                positional = helper.args.args
                for arg, default in zip(positional[-len(helper.args.defaults):], helper.args.defaults):
                    local[arg.arg] = ev(default)
                for arg, value in zip(positional, node.args):
                    local[arg.arg] = ev(value)
                extra = {}
                for kw in node.keywords:
                    if kw.arg in {arg.arg for arg in positional + helper.args.kwonlyargs}:
                        local[kw.arg] = ev(kw.value)
                    else:
                        extra[kw.arg] = ev(kw.value)
                if helper.args.kwarg:
                    local[helper.args.kwarg.arg] = extra
                for statement in helper.body:
                    if isinstance(statement, ast.Assign):
                        value = evaluate(statement.value, local)
                        for target in statement.targets:
                            assign(target, value, local)
                        if name == "placed_resistors" and any(isinstance(target, ast.Name) and target.id == "source" for target in statement.targets):
                            return value
                    elif isinstance(statement, ast.If):
                        for child in statement.body if evaluate(statement.test, local) else statement.orelse:
                            if isinstance(child, ast.Assign):
                                for target in child.targets:
                                    assign(target, evaluate(child.value, local), local)
                    elif isinstance(statement, ast.Return):
                        # placed_resistors also returns a backend model and layout.
                        returned = statement.value.elts[0] if name == "placed_resistors" else statement.value
                        return evaluate(returned, local)
        raise Unresolved(f"Dynamic expression: {ast.unparse(node)[:100]}")

    def remember(node, env):
        is_dict = isinstance(node, ast.Dict) and any(isinstance(key, ast.Constant) and key.value in {"components", "wires", "nodes", "edges"} for key in node.keys)
        name = node.func.id if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) else ""
        if not is_dict and name not in helpers and name not in consumers:
            return
        if name == "component":
            return
        expression = node.args[0] if name in consumers and node.args else node
        try:
            value = evaluate(expression, env)
            if isinstance(value, dict) and any(key in value for key in ("components", "nodes", "wires", "edges")) or name in consumers and value in (None, []):
                found.append({"line": node.lineno, "input": copy.deepcopy(value)})
        except (Unresolved, TypeError, KeyError, IndexError, ValueError) as exc:
            unresolved.append({"line": node.lineno, "expression": ast.unparse(expression), "reason": str(exc)})

    def invalidate(statements, env):
        for statement in statements:
            for node in ast.walk(statement):
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                    env.pop(node.id, None)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                    if node.func.attr in {"append", "extend", "pop", "reverse", "clear", "update"}:
                        env.pop(node.func.value.id, None)

    def walk(statements, env):
        for statement in statements:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if getattr(statement, "name", "") not in helpers:
                    walk(statement.body, dict(env))
                continue
            if isinstance(statement, ast.For):
                try:
                    values = list(evaluate(statement.iter, env))
                    if len(values) > 1000:
                        raise Unresolved("Loop limit")
                    for value in values:
                        local = copy.deepcopy(env)
                        assign(statement.target, value, local)
                        walk(statement.body, local)
                        env.update(local)
                except (Unresolved, TypeError, KeyError, IndexError, ValueError):
                    invalidate(statement.body, env)
                    walk(statement.body, copy.deepcopy(env))
                continue
            if isinstance(statement, (ast.With, ast.If, ast.Try)):
                walk(statement.body, env)
                walk(getattr(statement, "orelse", []), dict(env))
                continue
            if isinstance(statement, (ast.Assign, ast.AnnAssign)):
                try:
                    value = evaluate(statement.value, env)
                    for target in statement.targets if isinstance(statement, ast.Assign) else [statement.target]:
                        assign(target, value, env)
                except (Unresolved, TypeError, KeyError, IndexError, ValueError):
                    invalidate([statement], env)
            if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call) and isinstance(statement.value.func, ast.Attribute):
                call = statement.value
                try:
                    owner = evaluate(call.func.value, env)
                    method = call.func.attr
                    allowed = {"append", "extend", "pop", "reverse", "clear"} if isinstance(owner, list) else {"update", "pop", "clear"} if isinstance(owner, dict) else set()
                    if method in allowed:
                        getattr(owner, method)(*[evaluate(arg, env) for arg in call.args],
                                               **{kw.arg: evaluate(kw.value, env) for kw in call.keywords})
                except (Unresolved, TypeError, KeyError, IndexError, ValueError):
                    pass
            for node in ast.walk(statement):
                remember(node, env)
    walk(tree.body, {"ERROR": "error", "WARNING": "warning"})
    resolved_lines = {item["line"] for item in found}
    unique = {(item["line"], item["expression"]): item for item in unresolved if item["line"] not in resolved_lines}
    return found, sorted(unique.values(), key=lambda item: (item["line"], item["expression"]))

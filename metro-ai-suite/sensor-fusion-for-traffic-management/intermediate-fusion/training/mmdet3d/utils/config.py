import ast
import copy
import operator

__all__ = ["recursive_eval"]


_SAFE_BINARY_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
}

_SAFE_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _resolve_attribute(value, attr):
    if isinstance(value, dict) and attr in value:
        return value[attr]
    return getattr(value, attr)


def _resolve_slice(node, scope):
    if isinstance(node, ast.Slice):
        lower = _safe_eval_node(node.lower, scope) if node.lower is not None else None
        upper = _safe_eval_node(node.upper, scope) if node.upper is not None else None
        step = _safe_eval_node(node.step, scope) if node.step is not None else None
        return slice(lower, upper, step)
    return _safe_eval_node(node, scope)


def _safe_eval_node(node, scope):
    if isinstance(node, ast.Expression):
        return _safe_eval_node(node.body, scope)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return scope[node.id]
    if isinstance(node, ast.Attribute):
        return _resolve_attribute(_safe_eval_node(node.value, scope), node.attr)
    if isinstance(node, ast.List):
        return [_safe_eval_node(element, scope) for element in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_safe_eval_node(element, scope) for element in node.elts)
    if isinstance(node, ast.Dict):
        return {
            _safe_eval_node(key, scope): _safe_eval_node(value, scope)
            for key, value in zip(node.keys, node.values)
        }
    if isinstance(node, ast.Subscript):
        return _safe_eval_node(node.value, scope)[_resolve_slice(node.slice, scope)]
    if isinstance(node, ast.BinOp):
        op = _SAFE_BINARY_OPS.get(type(node.op))
        if op is None:
            raise ValueError(f"Unsupported expression operator: {ast.dump(node.op)}")
        return op(_safe_eval_node(node.left, scope), _safe_eval_node(node.right, scope))
    if isinstance(node, ast.UnaryOp):
        op = _SAFE_UNARY_OPS.get(type(node.op))
        if op is None:
            raise ValueError(f"Unsupported expression operator: {ast.dump(node.op)}")
        return op(_safe_eval_node(node.operand, scope))
    raise ValueError(f"Unsupported expression syntax: {ast.dump(node)}")


def _safe_eval_expr(expr, scope):
    tree = ast.parse(expr, mode="eval")
    return _safe_eval_node(tree, scope)


def recursive_eval(obj, globals=None):
    if globals is None:
        globals = copy.deepcopy(obj)

    if isinstance(obj, dict):
        for key in obj:
            obj[key] = recursive_eval(obj[key], globals)
    elif isinstance(obj, list):
        for k, val in enumerate(obj):
            obj[k] = recursive_eval(val, globals)
    elif isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
        obj = _safe_eval_expr(obj[2:-1], globals)
        obj = recursive_eval(obj, globals)

    return obj

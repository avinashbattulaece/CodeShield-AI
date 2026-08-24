import ast
import io
import re
import tokenize

def strip_comments(code):
    try:
        tokens = tokenize.generate_tokens(io.StringIO(code).readline)
        return "".join(
            token.string
            for token in tokens
            if token.type not in (tokenize.COMMENT, tokenize.ENCODING)
        )
    except Exception:
        return re.sub(r"#.*", "", code)

class PythonNormalizer(ast.NodeTransformer):
    def __init__(self):
        self.names = {}
        self.counter = 0

    def _name(self, value):
        if value not in self.names:
            self.counter += 1
            self.names[value] = f"VAR{self.counter}"
        return self.names[value]

    def visit_Name(self, node):
        return ast.copy_location(ast.Name(id=self._name(node.id), ctx=node.ctx), node)

    def visit_arg(self, node):
        return ast.copy_location(
            ast.arg(arg=self._name(node.arg), annotation=None, type_comment=None),
            node
        )

    def visit_FunctionDef(self, node):
        node.name = self._name(node.name)
        self.generic_visit(node)
        return node

    visit_AsyncFunctionDef = visit_FunctionDef

def normalize_python(code):
    try:
        tree = ast.parse(code)
        tree = PythonNormalizer().visit(tree)
        ast.fix_missing_locations(tree)
        return ast.dump(tree, annotate_fields=True, include_attributes=False)
    except Exception:
        return normalize_generic(code)

def normalize_generic(code):
    code = re.sub(r"//.*?$|#.*?$", "", code, flags=re.MULTILINE)
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
    code = re.sub(r"\b[_A-Za-z]\w*\b", "ID", code)
    code = re.sub(r"\b\d+(?:\.\d+)?\b", "NUM", code)
    code = re.sub(r"\s+", " ", code).strip()
    return code

def normalized_code(code, filename=""):
    if filename.lower().endswith(".py"):
        return normalize_python(code)
    return normalize_generic(code)

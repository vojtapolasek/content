from .ext.boolean import boolean
from .ext.packaging import version, specifiers


# We don't support ~= to avoid confusion with boolean operator NOT (~)
SPECIFIER_SYMBOLS = ['<', '>', '=', '!']

VERSION_SYMBOLS = ['.', '-', '_', '*']

SPECIFIER_OP_ID_TRANSLATION = {
    '==': 'eq',
    '!=': 'ne',
    '>': 'gt',
    '<': 'le',
    '>=': 'gt_or_eq',
    '<=': 'le_or_eq',
}


class Function(boolean.Function):
    """
    Base class for boolean functions

    Sub-class it and pass to the `Algebra` as `function_cls` to enrich
    expression elements with domain-specific methods.

    Provides `is_and`, `is_or` and `is_not` methods to distinguish instances
    between different boolean functions.

    The `as_id` method will generate an unique string identifier usable as
    an XML id based on the properties of the entity.
    """

    def is_and(self):
        return isinstance(self, boolean.AND)

    def is_or(self):
        return isinstance(self, boolean.OR)

    def is_not(self):
        return isinstance(self, boolean.NOT)

    def as_id(self):
        if self.is_not():
            return 'not_{0}'.format(self.args[0].as_id())
        op = 'unknown_bool_op'
        if self.is_and():
            op = 'and'
        if self.is_or():
            op = 'or'
        return '_{0}_'.format(op).join([arg.as_id() for arg in self.args])


class Symbol(boolean.Symbol):
    """
    Base class for boolean symbols

    Sub-class it and pass to the `Algebra` as `symbol_cls` to enrich
    expression elements with domain-specific methods.

    The `as_id` method will generate an unique string identifier usable as
    an XML id based on the properties of the entity.
    """

    def __init__(self, obj):
        super(Symbol, self).__init__(obj)
        idx = len(obj)
        for s in SPECIFIER_SYMBOLS:
            i = obj.find(s)
            if i < 0:
                continue
            idx = min(i, idx)
        if len(obj) > idx > 0:
            self.obj, spec = obj[:idx], obj[idx:]
            self.spec = specifiers.Specifier(spec)
        elif idx == len(obj):
            self.obj = obj
            self.spec = None
        else:
            raise "Invalid versioned symbol identifier: '{0}'".format(obj)

    def __call__(self, **kwargs):
        val = kwargs.get(self.obj, '')
        if val:
            if self.spec is not None:
                if type(val) is str:
                    return self.spec.contains(version.Version(val))
                return False
            return True
        return False

    def as_id(self):
        name = self.obj
        if self.spec is not None:
            spec = SPECIFIER_OP_ID_TRANSLATION.get(self.spec.operator, 'unknown_spec_op')
            ver = self.spec.version
            return '{0}_{1}_{2}'.format(name, spec, ver)
        return name


class Algebra(boolean.BooleanAlgebra):
    def __init__(self, symbol_cls, function_cls):
        not_cls = type('FunctionNOT', (function_cls, boolean.NOT), {})
        and_cls = type('FunctionAND', (function_cls, boolean.AND), {})
        or_cls = type('FunctionOR', (function_cls, boolean.OR), {})
        super(Algebra, self).__init__(allowed_in_token=VERSION_SYMBOLS+SPECIFIER_SYMBOLS,
                                      Symbol_class=symbol_cls,
                                      NOT_class=not_cls, AND_class=and_cls, OR_class=or_cls)

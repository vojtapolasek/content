import pytest

from ssg import boolean_expression
from xml.dom import expatbuilder


class PlatformFunction(boolean_expression.Function):
    def as_cpe_lang_xml(self):
        return '<cpe-lang:logical-test negate="' + ('true' if self.is_not() else 'false') + \
               '" operator="' + ('OR' if self.is_or() else 'AND') + '">' + \
               ''.join([arg.as_cpe_lang_xml() for arg in self.args]) + "</cpe-lang:logical-test>"


class PlatformSymbol(boolean_expression.Symbol):
    def as_cpe_lang_xml(self):
        return '<cpe-lang:fact-ref name="cpe:/a:' + self.obj + (':' + self.spec.version if self.spec else '') + '"/>'


class PlatformAlgebra(boolean_expression.Algebra):
    def __init__(self):
        super(PlatformAlgebra, self).__init__(symbol_cls=PlatformSymbol, function_cls=PlatformFunction)

    @staticmethod
    def as_cpe_lang_xml(expr):
        s = '<cpe-lang:platform id="' + expr.as_id() + '">' + expr.as_cpe_lang_xml() + '</cpe-lang:platform>'
        # A primitive but simple way to pretty-print an XML string
        return expatbuilder.parseString(s, False).toprettyxml()


@pytest.fixture
def algebra():
    return PlatformAlgebra()


@pytest.fixture
def algebra_dyn():
    return boolean_expression.Algebra(symbol_cls=PlatformSymbol, function_cls=PlatformFunction)


@pytest.fixture
def exp_simple(algebra):
    return algebra.parse(u'(oranges==2.0 | banana) and not not apple or !pie', simplify=True)


def test_dyn(algebra_dyn):
    exp = algebra_dyn.parse('not banana and not apple or anything')
    assert str(exp) == '(~banana&~apple)|anything'
    exp_s = exp.simplify()
    assert str(exp_s) == 'anything|(~apple&~banana)'


def test_evaluate_simple_boolean_ops(exp_simple):
    assert exp_simple(**{'oranges': '2.0', 'apple': True, 'pie': True})
    assert not exp_simple(**{'oranges': '2.0', 'apple': False, 'pie': True})


def test_evaluate_simple_version_ops(exp_simple):
    assert exp_simple(**{'oranges': '2', 'apple': True, 'pie': True})
    assert not exp_simple(**{'oranges': True, 'apple': True, 'pie': True})
    assert not exp_simple(**{'oranges': '2.0.1', 'apple': True, 'pie': True})
    assert not exp_simple(**{'oranges': '3.0', 'apple': True, 'pie': True})


def test_cnf(algebra, exp_simple):
    assert str(algebra.cnf(exp_simple)) == '(apple|~pie)&(banana|oranges|~pie)'


def test_dnf(algebra, exp_simple):
    assert str(algebra.dnf(exp_simple)) == '~pie|(apple&banana)|(apple&oranges)'


def test_as_cpe_xml(algebra, exp_simple):
    xml = algebra.as_cpe_lang_xml(algebra.dnf(exp_simple))
    assert xml == '''<?xml version="1.0" ?>
<cpe-lang:platform id="not_pie_or_apple_and_banana_or_apple_and_oranges_eq_2.0">
	<cpe-lang:logical-test negate="false" operator="OR">
		<cpe-lang:logical-test negate="true" operator="AND">
			<cpe-lang:fact-ref name="cpe:/a:pie"/>
		</cpe-lang:logical-test>
		<cpe-lang:logical-test negate="false" operator="AND">
			<cpe-lang:fact-ref name="cpe:/a:apple"/>
			<cpe-lang:fact-ref name="cpe:/a:banana"/>
		</cpe-lang:logical-test>
		<cpe-lang:logical-test negate="false" operator="AND">
			<cpe-lang:fact-ref name="cpe:/a:apple"/>
			<cpe-lang:fact-ref name="cpe:/a:oranges:2.0"/>
		</cpe-lang:logical-test>
	</cpe-lang:logical-test>
</cpe-lang:platform>
'''

"""Parser, Formatierung und Op-Schlüssel (kmx.ops)."""

import kmx
from tests.kmx.helpers import (
    HEAD,
    fmt,
    raises,
)


def test_parser_accepts_plain_gate_lines():
    op = kmx.parse_line("CCX q0 q1 q2")
    assert (op.name, op.args, op.qs, op.cond, op.bit, op.text) == (
        "CCX",
        ("q0", "q1", "q2"),
        (0, 1, 2),
        None,
        None,
        None,
    )
    assert kmx.parse_line("HMR q4 b7").bit == 7 and kmx.parse_line("HMR q4 b7").qs == (
        4,
    )
    assert (
        kmx.parse_line("NEG").args == ()
        and kmx.parse_line("POP_CONDITION").name == "POP_CONDITION"
    )
    assert kmx.parse_line("Z_POW q3 -0.125").args == ("q3", "-0.125")
    assert kmx.parse_line("BIT_STORE1 b2").bit == 2


def test_parser_reads_trailing_condition():
    op = kmx.parse_line("CZ q0 q1 if b3")
    assert op.cond == 3 and op.qs == (0, 1) and op.fmt() == "CZ q0 q1 if b3"
    assert kmx.parse_line("Z_POW q0 0.5 if b0").cond == 0
    assert kmx.parse_line("PUSH_CONDITION if b5").cond == 5


def test_parser_tolerates_v1_push_condition_and_emits_v2():
    op = kmx.parse_line("PUSH_CONDITION b3")
    assert op.cond == 3 and op.args == () and op.fmt() == "PUSH_CONDITION if b3"


def test_parser_skips_comments_and_blank_lines():
    assert kmx.parse_line("# nur Kommentar") is None and kmx.parse_line("   ") is None
    assert kmx.parse_line("X q0   # danach").fmt() == "X q0"
    ops = kmx.parse_text("# a\n\nX q0\n  CX q0 q1 # b\n")
    assert fmt(ops) == ["X q0", "CX q0 q1"]


def test_parser_keeps_quoted_text():
    reg = kmx.parse_line('REGISTER r0 "x"')
    tag = kmx.parse_line('INFO_TAG "@enter:adder stage"')
    assert reg.text == '"x"' and reg.args == ("r0",) and reg.fmt() == 'REGISTER r0 "x"'
    assert tag.text == '"@enter:adder stage"' and tag.args == ()


def test_parser_rejects_duplicate_qubits():
    for line in (
        "CX q0 q0",
        "CCX q0 q1 q0",
        "SWAP q2 q2",
        "CSWAP q1 q1 q2",
        "CZ q3 q3",
    ):
        e = raises(kmx.KmxError, kmx.parse_line, line)
        assert "mehrfach" in str(e), line


def test_parser_rejects_unknown_ops_and_wrong_arity():
    assert "unbekannte Instruktion" in str(raises(kmx.KmxError, kmx.parse_line, "T q0"))
    assert "unbekannte Instruktion" in str(raises(kmx.KmxError, kmx.parse_line, "x q0"))
    for line in (
        "X",
        "X q0 q1",
        "CX q0",
        "CX q0 b1",
        "HMR q0 q1",
        "HMR q0",
        "NEG q0",
        "BIT_STORE0 q0",
        "PUSH_CONDITION",
        "POP_CONDITION if b0",
        "X b0",
    ):
        raises(kmx.KmxError, kmx.parse_line, line)


def test_parser_rejects_fraction_and_exponent_notation_angles():
    for angle in ("1/4", "1e-3", "2.5E-1", ".5", "5.", "0x1", "pi"):
        e = raises(kmx.KmxError, kmx.parse_line, f"Z_POW q0 {angle}")
        assert "Z_POW" in str(e), angle
    for angle in ("0.25", "-0.75", "+0.5", "12.000390625"):
        assert kmx.parse_line(f"Z_POW q0 {angle}").args[1] == angle


def test_parser_rejects_bad_conditions():
    assert "Bedingung" in str(raises(kmx.KmxError, kmx.parse_line, "X q0 if q1"))
    assert "Bedingung" in str(raises(kmx.KmxError, kmx.parse_line, "X q0 if 1"))
    raises(kmx.KmxError, kmx.parse_line, "X q0 if")
    raises(kmx.KmxError, kmx.parse_line, "X q0 if b1 if b2")


def test_parse_errors_carry_line_number_and_non_strings_are_rejected():
    e = raises(kmx.KmxError, kmx.parse_text, "X q0\nCX q1 q1\n")
    assert "Zeile 2" in str(e)
    e = raises(kmx.KmxError, kmx.parse_lines, ["X q0", 5])
    assert "Eintrag 1" in str(e)


def test_format_ops_roundtrips_through_parser():
    text = (
        HEAD
        + "CCX q0 q1 q8\nHMR q8 b0\nCZ q0 q1 if b0\nPUSH_CONDITION if b0\nZ_POW q2 "
        "-0.25\nPOP_CONDITION\nNEG\n"
    )
    assert kmx.format_ops(kmx.parse_text(text)) == text


def test_op_key_canonicalises_symmetric_arguments():
    def key(s):
        return kmx.parse_line(s).key()

    assert key("CZ q1 q0") == key("CZ q0 q1")
    assert key("CCZ q2 q0 q1") == key("CCZ q0 q1 q2")
    assert key("SWAP q4 q3") == key("SWAP q3 q4")
    assert key("CCX q1 q0 q2") == key("CCX q0 q1 q2")
    assert key("CSWAP q0 q2 q1") == key("CSWAP q0 q1 q2")


def test_op_key_keeps_order_where_it_matters():
    def key(s):
        return kmx.parse_line(s).key()

    assert key("CX q0 q1") != key("CX q1 q0")
    assert key("CCX q0 q2 q1") != key("CCX q0 q1 q2")  # anderes Ziel
    assert key("CSWAP q1 q0 q2") != key("CSWAP q0 q1 q2")  # andere Kontrolle
    assert key("CZ q0 q1 if b0") != key("CZ q0 q1")
    assert key("CZ q0 q1 if b0") != key("CZ q0 q1 if b1")
    assert key("Z_POW q0 0.25") != key("Z_POW q0 0.5")


def test_op_renamed_maps_qubits_only():
    op = kmx.parse_line("HMR q8 b8 if b3")
    zp = kmx.parse_line("Z_POW q8 0.125")
    # Bit b8 bleibt, nur q8 wandert
    assert op.renamed({8: 6}).fmt() == "HMR q6 b8 if b3"
    assert zp.renamed({8: 2}).fmt() == "Z_POW q2 0.125"
    assert kmx.parse_line("CCX q1 q2 q3").renamed({1: 3, 3: 1}).fmt() == "CCX q3 q2 q1"
    assert op.renamed({5: 6}) is op  # nichts betroffen: dasselbe Objekt
    assert op.fmt() == "HMR q8 b8 if b3"  # Original unveraendert


def test_parser_rejects_integer_zpow_exponent():
    # Regression: kickmix verlangt [-+]?[0-9]+\.[0-9]+ (siehe Docstring von phase_op);
    # _EXP_RE liess "Z_POW q0 1" durch. Ueber propose_rewrite kann so eine Zeile
    # verifiziert in die Ausgabedatei gelangen, die kickmix nicht parst.
    raises(kmx.KmxError, kmx.parse_line, "Z_POW q0 1")


def test_parser_keeps_hash_inside_quoted_text():
    # Regression: '#' im Text schnitt die Zeile ab und hinterliess einen offenen String;
    # kickmix liest es als Zeichen.
    assert kmx.parse_line('INFO_TAG "a # b"  # Kommentar').text == '"a # b"'
    raises(kmx.KmxError, kmx.parse_line, 'INFO_TAG "a')
    raises(kmx.KmxError, kmx.parse_line, 'INFO_TAG "a"b"')

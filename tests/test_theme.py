"""Tests for the HTML fragments in nassau.theme (no Streamlit or Plotly needed)."""
import unittest

from nassau import theme


class ThemeTests(unittest.TestCase):
    def test_names_are_escaped(self):
        html = theme.hero_html('<img src=x onerror=alert(1)>', '<b>Admin</b>')
        self.assertNotIn("<img", html)
        self.assertNotIn("<b>Admin", html)
        self.assertIn("&lt;img", html)

    def test_initials(self):
        self.assertEqual(theme.initials("Alice Rao"), "AR")
        self.assertEqual(theme.initials("bob"), "B")
        self.assertEqual(theme.initials("carol.d-smith"), "CD")
        self.assertEqual(theme.initials("   "), "?")

    def test_kpi_strip_values_and_bar(self):
        html = theme.kpi_strip_html({"Sales": 141783.63, "GrossProfit": 93442.8, "GrossMargin": 0.659,
                                     "ProfitPerUnit": 2.417, "Units": 38654, "Orders": 8549})
        for text in ("$141,784", "$93,443", "65.9%", "$2.42", "38,654", "8,549", "--w:65.9%"):
            self.assertIn(text, html)

    def test_margin_bar_is_clamped(self):
        html = theme.kpi_strip_html({"Sales": 1, "GrossProfit": 2, "GrossMargin": 2.0, "ProfitPerUnit": 1,
                                     "Units": 1, "Orders": 1})
        self.assertIn("--w:100.0%", html)

    def test_fragments_are_single_line_so_markdown_keeps_them_html(self):
        for html in (theme.login_brand_html(), theme.hero_html("A", "Admin"), theme.sidebar_brand_html()):
            self.assertNotIn("\n", html)


if __name__ == "__main__":
    unittest.main()

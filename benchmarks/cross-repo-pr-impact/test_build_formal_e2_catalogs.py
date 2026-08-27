import unittest

from build_formal_e2_catalogs import parse_starlingx_manifest


class FormalE2CatalogBuilderTests(unittest.TestCase):
    def test_manifest_uses_only_official_starlingx_remote(self):
        xml = '''<manifest>
          <project remote="starlingx" name="config.git" path="stx/config"/>
          <project remote="openstack" name="nova.git" path="stx/nova"/>
          <project remote="starlingx" name="integ.git" path="stx/integ"/>
        </manifest>'''
        self.assertEqual(
            ["starlingx/config", "starlingx/integ", "starlingx/manifest"],
            parse_starlingx_manifest(xml),
        )


if __name__ == "__main__":
    unittest.main()

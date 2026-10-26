import tempfile,unittest
from pathlib import Path
from configure_baseline import install
from audit_accuracy import ini
FIXTURES=Path(__file__).resolve().parents[1]/"private/baseline-tests"
FIXTURES.mkdir(parents=True,exist_ok=True)

class BaselineTests(unittest.TestCase):
    def test_preserves_save_input_and_unrelated_settings_and_backs_up(self):
        with tempfile.TemporaryDirectory(dir=FIXTURES) as temp:
            root=Path(temp);(root/'Config').mkdir();save=root/'progress.gci';save.write_bytes(b'preserved')
            pad=root/'Config/GCPadNew.ini';pad.write_text('[GCPad1]\nButtons/A = custom\n')
            gfx=root/'Config/GFX.ini';original='[Settings]\nAspectRatio=0\nInternalResolution=3\n[Hacks]\nCustomFlag=True\n';gfx.write_text(original)
            changes=install(root);self.assertEqual(len(changes),2)
            self.assertEqual(Path(changes[1]['backup']).read_text(),original)
            self.assertEqual(save.read_bytes(),b'preserved');self.assertIn('custom',pad.read_text())
            c=ini(gfx);self.assertEqual(c.get('Settings','AspectRatio'),'2');self.assertEqual(c.get('Hacks','CustomFlag'),'True')
            self.assertEqual(install(root),[])
    def test_case_insensitive_existing_keys(self):
        with tempfile.TemporaryDirectory(dir=FIXTURES) as temp:
            root=Path(temp);(root/'Config').mkdir();path=root/'Config/GFX.ini'
            path.write_text('[Settings]\naspectratio=0\ninternalresolution=3\n')
            install(root);c=ini(path);self.assertEqual(c.get('Settings','AspectRatio'),'2')
            self.assertEqual(sum(k.lower()=='aspectratio' for k in c['Settings']),1)

if __name__=='__main__':unittest.main()

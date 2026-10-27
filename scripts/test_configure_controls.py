import configparser
from pathlib import Path
import unittest
from uuid import uuid4
from configure_controls import ROOT,install,migrate,legacy_profile,profile

class ControllerConfigTests(unittest.TestCase):
    def setUp(self):
        self.user=ROOT/'build/control-config-tests'/uuid4().hex
        (self.user/'Config').mkdir(parents=True)
    def test_fresh_profile_and_gamecube_port(self):
        report=install(self.user)
        c=configparser.ConfigParser();c.read(report['profile'])
        self.assertEqual(c['GCPad1']['Options/Always Connected'],'True')
        d=configparser.ConfigParser();d.read(self.user/'Config/Dolphin.ini')
        self.assertEqual(d['Core']['SIDevice0'],'6')
    def test_other_controller_preserved(self):
        p=self.user/'Config/GCPadNew.ini';p.write_text('[GCPad2]\nDevice=custom\nButtons/A=special\n')
        install(self.user);c=configparser.ConfigParser();c.read(p)
        self.assertEqual(c['GCPad2']['Device'],'custom');self.assertEqual(c['GCPad2']['Buttons/A'],'special')
    def test_previous_profile_backed_up(self):
        p=self.user/'Config/GCPadNew.ini';before=b'[GCPad1]\nDevice=previous\n';p.write_bytes(before)
        v=install(self.user);self.assertEqual(Path(v['previous_profile_backup']).read_bytes(),before)
    def test_idempotent(self):
        first=install(self.user);before=Path(first['profile']).read_bytes();second=install(self.user)
        self.assertIsNone(second['previous_profile_backup']);self.assertEqual(Path(first['profile']).read_bytes(),before)
    def test_saves_and_other_settings_untouched(self):
        (self.user/'GC').mkdir();save=self.user/'GC/synthetic.gci';save.write_bytes(b'KEEP MY SAVE')
        d=self.user/'Config/Dolphin.ini';d.write_text('[Core]\nSlotA=8\nSIDevice1=7\n[DSP]\nVolume=23\n')
        install(self.user);c=configparser.ConfigParser();c.read(d)
        self.assertEqual(save.read_bytes(),b'KEEP MY SAVE');self.assertEqual(c['Core']['SlotA'],'8');self.assertEqual(c['Core']['SIDevice1'],'7');self.assertEqual(c['DSP']['Volume'],'23')

    def test_gamecube_layout_and_rumble(self):
        report=install(self.user)
        c=configparser.ConfigParser(interpolation=None);c.optionxform=str;c.read(report['profile'])
        self.assertIn('Gamepad:Button X`',c['GCPad1']['Buttons/B'])
        self.assertIn('Gamepad:Button B`',c['GCPad1']['Buttons/X'])
        self.assertIn('Gamepad:Motor L`',c['GCPad1']['Rumble/Motor'])
        self.assertIn('Gamepad:Motor R`',c['GCPad1']['Rumble/Motor'])
    def test_migrate_old_defaults_keeps_custom(self):
        p=self.user/'Config/GCPadNew.ini'
        c=configparser.ConfigParser(interpolation=None);c.optionxform=str;c.add_section('GCPad1')
        for key,value in legacy_profile().items():c.set('GCPad1',key,value)
        c.set('GCPad1','Buttons/Y','`XInput/0/Gamepad:Thumb L`')
        with p.open('w',encoding='utf-8') as out:c.write(out)
        before=p.read_bytes();report=migrate(self.user)
        self.assertEqual(Path(report['previous_profile_backup']).read_bytes(),before)
        m=configparser.ConfigParser(interpolation=None);m.optionxform=str;m.read(p)
        self.assertEqual(m['GCPad1']['Buttons/B'],profile()['Buttons/B'])
        self.assertEqual(m['GCPad1']['Buttons/X'],profile()['Buttons/X'])
        self.assertEqual(m['GCPad1']['Rumble/Motor'],profile()['Rumble/Motor'])
        self.assertEqual(m['GCPad1']['Buttons/Y'],'`XInput/0/Gamepad:Thumb L`')
        self.assertIn('Buttons/Y',report['kept_custom'])
        again=migrate(self.user);self.assertIsNone(again['previous_profile_backup']);self.assertEqual(again['updated'],[])

if __name__=='__main__':unittest.main()

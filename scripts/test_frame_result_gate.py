"""Regression checks: SR-only/stale/corrupted results cannot become NR evidence."""
import hashlib,json,tempfile,unittest
from pathlib import Path
from verify_frame_result import validate_payload,verify

class ResultGate(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.color=bytes([40,60,80,255])*(96*96)
        arrays={'color.rgba8':self.color,'depth.f32':b'\0'*96*96*4,'motion.f16':b'\0'*96*96*4}
        files={}
        for name,data in arrays.items():
            (self.root/name).write_bytes(data);files[name]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
        (self.root/'payload.json').write_text(json.dumps({'schema':1,'size':[96,96],'files':files,'origin':'top-left','reset':True}))
        (self.root/'ngx_output.rgba8').write_bytes(self.color)
        self.log=self.root/'ReShade.log';self.log.write_text('NGX evaluate succeeded')
    def test_sr_only_rejected(self):
        with self.assertRaisesRegex(ValueError,'No explicit'):verify(self.root,self.log,0)
        self.assertFalse((self.root/'after.png').exists())
    def test_crash_with_old_success_rejected(self):
        self.log.write_text('inline feature 18 evaluation succeeded (count=1)')
        with self.assertRaisesRegex(ValueError,'Host failed'):verify(self.root,self.log,1)
    def test_corrupted_input_rejected(self):
        (self.root/'color.rgba8').write_bytes(bytes(len(self.color)))
        with self.assertRaisesRegex(ValueError,'checksum'):validate_payload(self.root)
    def test_wrong_output_size_rejected(self):
        (self.root/'ngx_output.rgba8').write_bytes(b'bad')
        with self.assertRaisesRegex(ValueError,'Output dimensions'):verify(self.root,self.log,0)
    def test_nr_success_does_not_claim_quality(self):
        self.log.write_text('inline feature 18 evaluation succeeded (count=1)')
        result=verify(self.root,self.log,0)
        self.assertTrue(result['nr_confirmed']);self.assertFalse(result['quality_improvement_confirmed'])
        self.assertEqual(result['changed_rgb_channels'],0)

if __name__=='__main__':unittest.main()


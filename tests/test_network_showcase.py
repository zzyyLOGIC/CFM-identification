"""v2.1 standalone showcase: presentation must not silently mix studies."""
import unittest
import json
from examples.render_network_showcase import combine, make_html


class ShowcaseAssemblyV21Tests(unittest.TestCase):
    def setUp(self):
        self.r1a=dict(graph_fingerprint='graph-A',node_count=3,arm_count=12,
            point_arm_count=12,batch_sha256='sha',source_spec_sha256='source',
            arm_matrix_status=[[['POINT','POINT'],['POINT','POINT']]]*3,
            arm_matrix_support_exact=[[['1/4','1/4'],['1/4','1/4']]]*3,
            arm_matrix_support=[[[.25,.25],[.25,.25]]]*3,
            arm_labels=['T=0,S=0','T=0,S=1','T=1,S=0','T=1,S=1'],
            business_cases=[dict(status='POINT',title='case1')])
        self.r1b=dict(graph_fingerprint='graph-A',business_cases=[dict(status='NEEDS_INPUT',title='case2')])
        self.r2=dict(graph_fingerprint='graph-A',business_cases=[dict(status='POINT',title='case3')])

    def test_combiner_only_presents_precomputed_results(self):
        out=combine({'r1a':self.r1a,'r1b':self.r1b,'r2':self.r2},False)
        self.assertEqual((out['business_verified'],out['business_rejected']),(2,1))
        self.assertEqual((out['arm_count'],out['point_arm_count']),(12,12))

    def test_reject_mismatched_r1b_network(self):
        b={**self.r1b,'graph_fingerprint':'graph-B'}
        with self.assertRaisesRegex(ValueError,'R1a/R1b'):
            combine({'r1a':self.r1a,'r1b':b,'r2':self.r2},False)

    def test_reject_mismatched_er300_r2_network(self):
        a={**self.r1a,'node_count':300}
        b={**self.r2,'graph_fingerprint':'graph-B'}
        with self.assertRaisesRegex(ValueError,'R2 hypothetical D2'):
            combine({'r1a':a,'r1b':self.r1b,'r2':b},True)

    def test_er300_reject_incorrect_node_count(self):
        with self.assertRaisesRegex(ValueError,'300-node'):
            combine({'r1a':self.r1a,'r1b':self.r1b,'r2':self.r2},True)

    def test_html_json_escapes_script_termination(self):
        out=combine({'r1a':self.r1a,'r1b':self.r1b,'r2':self.r2},False)
        out['source_notes']={'bad':'</script><script>alert(1)</script>'}
        html=make_html(out)
        self.assertNotIn('</script><script>alert(1)</script>',html)
        self.assertIn('\\u003c/script>',html)
        self.assertIn('Causal-IDFM',html)


if __name__=='__main__':
    unittest.main()

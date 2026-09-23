import importlib.util
import pathlib
import unittest

path = pathlib.Path(__file__).parents[1] / 'tools/analyze-video-presentation.py'
spec = importlib.util.spec_from_file_location('presentation', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def sample(flags=5):
    lines = ['K230_PRESENT_CLOCK clock_id=1']
    for i in range(3):
        submit = 1_000_000_000 + i * 16_000_000_000
        lines.append(f'K230_SUBMIT serial={i} frame={i+1} pts={i:.9f} mono_ns={submit}')
        lines.append(f'K230_PRESENT serial={i} frame={i+1} pts={i:.9f} '
                     f'submit_mono_ns={submit} presented_ns={submit+1000000} '
                     f'receive_mono_ns={submit+2000000} refresh_ns=16666667 '
                     f'sequence={i*960} flags={flags}')
    return '\n'.join(lines)


class PresentationTest(unittest.TestCase):
    def test_counts_and_clock_units(self):
        result = module.analyze(sample())
        self.assertEqual(result['presentation_span_s'], 32)
        self.assertEqual(result['unique_presented_video_frames'], 3)
        self.assertEqual(result['submit_to_present_ms']['mean'], 1)
        self.assertTrue(result['all_hardware_completion'])

    def test_missing_hardware_flag_is_not_upgraded(self):
        self.assertFalse(module.analyze(sample(1))['all_hardware_completion'])

    def test_duplicate_feedback_rejected(self):
        with self.assertRaises(ValueError):
            module.analyze(sample() + '\n' + sample().splitlines()[-1])

    def test_missing_clock_rejected(self):
        with self.assertRaises(ValueError):
            module.analyze('\n'.join(sample().splitlines()[1:]))

    def test_frame_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            module.analyze(sample().replace('K230_PRESENT serial=0 frame=1',
                                           'K230_PRESENT serial=0 frame=9'))

    def test_discarded_and_pending_frames_are_distinct(self):
        text = sample() + ('\nK230_SUBMIT serial=3 frame=4 pts=3.000000000 mono_ns=50'
                           '\nK230_DISCARD serial=3 frame=4 pts=3.000000000 receive_mono_ns=60'
                           '\nK230_SUBMIT serial=4 frame=5 pts=4.000000000 mono_ns=70')
        result = module.analyze(text)
        self.assertEqual(result['discarded'], 1)
        self.assertEqual(result['unresolved_at_log_end'], 1)


if __name__ == '__main__':
    unittest.main()

import subprocess
res = subprocess.run(['python', '-m', 'pytest', '-s', 'tests/test_detection_engine.py::test_detection_engine_e2e'], capture_output=True, text=True, encoding='utf-8')
with open('debug_trace.txt', 'w', encoding='utf-8') as f:
    f.write(res.stdout)
    f.write(res.stderr)

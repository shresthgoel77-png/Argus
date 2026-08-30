import subprocess

print("=== 1. Starting test run 1 ===")
res1 = subprocess.run(['python', '-m', 'pytest', 'tests/test_detection_engine.py::test_detection_engine_e2e', '-v'], capture_output=True, text=True)

print("=== 2. Starting test run 2 ===")
res2 = subprocess.run(['python', '-m', 'pytest', 'tests/test_detection_engine.py::test_detection_engine_e2e', '-v'], capture_output=True, text=True)

with open('final_report.txt', 'w', encoding='utf-8') as f:
    f.write(f"Run 1 Code: {res1.returncode}\n")
    f.write(f"Run 2 Code: {res2.returncode}\n")
    f.write("---\nRUN 1:\n")
    f.write(res1.stdout)
    f.write("---\nRUN 2:\n")
    f.write(res2.stdout)

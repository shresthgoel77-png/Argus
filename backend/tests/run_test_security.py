import subprocess
with open('test_sec_out.txt', 'w', encoding='utf-8') as f:
    result = subprocess.run(['..\\\\.venv\\\\Scripts\\\\python.exe', '-m', 'pytest', 'tests/test_security.py', '-v'], capture_output=True, text=True)
    f.write(result.stdout)
    f.write("\n\nSTDERR:\n")
    f.write(result.stderr)

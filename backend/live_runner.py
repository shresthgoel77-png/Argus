import subprocess
print("Running live_flow.py...")
with open('live_out.txt', 'w', encoding='utf-8') as f:
    res = subprocess.run(['python', 'live_flow.py'], capture_output=True, text=True, encoding='utf-8')
    f.write(res.stdout)
    f.write(res.stderr)
print("Finished!")

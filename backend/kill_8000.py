import psutil

for proc in psutil.process_iter(['pid', 'name']):
    try:
        for conn in proc.connections(kind='inet'):
            if conn.laddr.port == 8000:
                print(f"Killing process {proc.info['name']} (PID: {proc.info['pid']})")
                proc.kill()
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        pass

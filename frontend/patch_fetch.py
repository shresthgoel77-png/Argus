import os
import glob

api_dir = r"c:\Users\HP\Desktop\.vscode\Argus  og\frontend\src\lib\api"

for filename in glob.glob(os.path.join(api_dir, "*.ts")):
    with open(filename, "r", encoding="utf-8") as f:
        content = f.read()
    
    if "clerkToken" in content:
        continue

    # inject the token lookup
    if "const mergedOptions: RequestInit = {" in content:
        content = content.replace(
            "const mergedOptions: RequestInit = {",
            'const clerkToken = typeof window !== "undefined" && (window as any).Clerk?.session ? await (window as any).Clerk.session.getToken() : null;\n    const mergedOptions: RequestInit = {'
        )
        
        # inject the header
        content = content.replace(
            '"Content-Type": "application/json",',
            '"Content-Type": "application/json",\n            ...(clerkToken ? { Authorization: `Bearer ${clerkToken}` } : {}),'
        )
        
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Patched: {filename}")

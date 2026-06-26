import json
import urllib.request
import urllib.parse
import os

def upload_file(url, file_path, field_name='file'):
    filename = os.path.basename(file_path)
    # Determine boundary
    boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
    
    # Read file content
    with open(file_path, 'rb') as f:
        file_content = f.read()
    
    # Build multipart/form-data payload
    parts = []
    parts.append(f'--{boundary}'.encode('utf-8'))
    parts.append(f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"'.encode('utf-8'))
    # Determine Content-Type
    if filename.endswith('.json'):
        parts.append(b'Content-Type: application/json')
    elif filename.endswith('.edi'):
        parts.append(b'Content-Type: text/plain')
    else:
        parts.append(b'Content-Type: application/octet-stream')
    parts.append(b'')
    parts.append(file_content)
    parts.append(f'--{boundary}--'.encode('utf-8'))
    parts.append(b'')
    
    body = b'\r\n'.join(parts)
    
    req = urllib.request.Request(url, data=body)
    req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
    req.add_header('Content-Length', str(len(body)))
    
    try:
        with urllib.request.urlopen(req) as response:
            status = response.status
            res_body = response.read().decode('utf-8')
            return status, json.loads(res_body)
    except urllib.error.HTTPError as e:
        status = e.code
        res_body = e.read().decode('utf-8')
        try:
            return status, json.loads(res_body)
        except Exception:
            return status, res_body
    except Exception as e:
        return 0, str(e)

if __name__ == '__main__':
    base_url = 'http://127.0.0.1:8000/api/v1/ingest'
    
    edi_path = r'd:\confluence\rag_validator\demo\sample_claim.edi'
    print(f"Uploading EDI file: {edi_path}")
    status, res = upload_file(base_url, edi_path)
    print(f"Status: {status}")
    print(json.dumps(res, indent=2))
    print("\n" + "="*50 + "\n")
    
    json_path = r'd:\confluence\rag_validator\demo\sample_claim.json'
    print(f"Uploading JSON file: {json_path}")
    status, res = upload_file(base_url, json_path)
    print(f"Status: {status}")
    print(json.dumps(res, indent=2))

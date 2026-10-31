from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
ROOT=Path(__file__).resolve().parent
class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs): super().__init__(*args,directory=str(ROOT),**kwargs)
    def log_message(self,*_): pass
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8770);args=parser.parse_args()
    with ThreadingHTTPServer(('127.0.0.1',args.port),Handler) as server:
        print('Frontend: http://127.0.0.1:'+str(args.port),flush=True);server.serve_forever()

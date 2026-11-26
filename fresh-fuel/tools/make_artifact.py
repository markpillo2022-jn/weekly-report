#!/usr/bin/env python3
"""Turn fresh-fuel/index.html into the body-only page the claude.ai Artifact preview expects.
Usage: python3 make_artifact.py fresh-fuel/index.html OUT_DIR   (then publish OUT_DIR/index.html with data.json beside it)"""
import re,sys,os,shutil
src=open(sys.argv[1]).read();out=sys.argv[2];os.makedirs(out,exist_ok=True)
head=src[src.index('<head>')+6:src.index('</head>')]
body=src[src.index('<body>')+6:src.index('</body>')]
head=re.sub(r'<meta (charset|name="viewport")[^>]*>\n?','',head)
head=head.replace('<title>','<meta name="claude:viewport-fit-sides" content="cover">\n<title>',1)
open(os.path.join(out,'index.html'),'w').write(head.strip()+'\n'+body.strip()+'\n')
shutil.copy(os.path.join(os.path.dirname(sys.argv[1]),'data.json'),os.path.join(out,'data.json'))

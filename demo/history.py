"""Private local conversation metadata and native snapshot storage."""
import hashlib,json,os,re,secrets,shutil
from pathlib import Path
from .media import MediaError

class HistoryStore:
    def __init__(self,root):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);self.root.chmod(0o700)
    def folder(self,key):
        if not isinstance(key,str) or not re.fullmatch('[a-f0-9]{32}',key):raise MediaError('unknown_session')
        return self.root/key
    def _ensure_folder(self,key):
        root=self.folder(key)
        root.mkdir(mode=0o700,exist_ok=True)
        return root
    def owner(self,token):
        if not isinstance(token,str) or not re.fullmatch('[a-f0-9]{64}',token):raise MediaError('unknown_session')
        return hashlib.sha256(token.encode()).hexdigest()
    def read(self,key):
        try:return json.loads((self.folder(key)/'conversation.json').read_text())
        except (OSError,ValueError):raise MediaError('unknown_session') from None
    def write(self,session):
        root=self._ensure_folder(session.id)
        data={key:getattr(session,key) for key in ['id','token','owner_hash','title','summary','system','turns','context','messages','snapshot','updated']}
        temporary=root/('.metadata-'+secrets.token_hex(8))
        fd=os.open(temporary,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        try:
            with os.fdopen(fd,'w') as f:json.dump(data,f,ensure_ascii=False);f.flush();os.fsync(f.fileno())
            os.replace(temporary,root/'conversation.json')
            directory_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:temporary.unlink(missing_ok=True)
    def list(self,owner_token):
        owner=self.owner(owner_token);rows=[]
        for file in self.root.glob('*/conversation.json'):
            try:data=json.loads(file.read_text())
            except (OSError,ValueError):continue
            if data.get('owner_hash')==owner and data.get('turns'):
                rows.append({k:data[k] for k in ['id','token','title','updated']})
        return sorted(rows,key=lambda d:d['updated'],reverse=True)
    def retain_upload(self,key,path):
        root=self._ensure_folder(key)/'media';root.mkdir(mode=0o700,exist_ok=True)
        name=secrets.token_hex(16)+path.suffix
        shutil.copyfile(path,root/name);(root/name).chmod(0o600)
        return name
    def media(self,key,name):
        if not isinstance(name,str) or not re.fullmatch('[a-f0-9]{32}\.(png|jpg|wav)',name):raise MediaError('unknown_media')
        path=self.folder(key)/'media'/name
        if not path.is_file() or path.is_symlink():raise MediaError('unknown_media')
        return path
    def new_snapshot(self,key):
        root=self._ensure_folder(key)/'kv';root.mkdir(mode=0o700,exist_ok=True)
        return root/('snapshot-'+secrets.token_hex(16))
    def prune_snapshots(self,session):
        root=self.folder(session.id)/'kv'
        entries=sorted((p for p in root.glob('snapshot-*') if p.is_dir() and not p.is_symlink()),key=lambda p:p.stat().st_mtime,reverse=True)
        for path in entries[2:]:
            if str(path.relative_to(self.folder(session.id)))!=session.snapshot:shutil.rmtree(path)

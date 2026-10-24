import hashlib
import importlib.util
import io
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('official_fetch', Path(__file__).parents[1]/'setup/fetch_official.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class Response(io.BytesIO):
    def geturl(self): return 'https://download.microsoft.com/test.exe'

class Opener:
    def __init__(self, data): self.data=data; self.calls=0
    def open(self, *args, **kwargs): self.calls+=1; return Response(self.data)

def asset(data):
    return dict(filename='test.exe', url='https://download.microsoft.com/test.exe', size=len(data), sha256=hashlib.sha256(data).hexdigest())

def test_corrupt_payload_never_promoted_and_retry_succeeds(tmp_path):
    a=asset(b'good')
    with pytest.raises(ValueError, match='mismatch'): m.fetch(a,tmp_path,Opener(b'evil'))
    assert list(tmp_path.iterdir())==[]
    opener=Opener(b'good')
    assert m.fetch(a,tmp_path,opener)=='downloaded_verified'
    assert m.fetch(a,tmp_path,opener)=='verified_cached'
    assert opener.calls==1

def test_existing_changed_file_and_symlink_are_preserved(tmp_path):
    a=asset(b'good');p=tmp_path/'test.exe';p.write_bytes(b'user')
    with pytest.raises(ValueError,match='differs'):m.fetch(a,tmp_path,Opener(b'good'))
    assert p.read_bytes()==b'user'
    p.unlink();target=tmp_path/'personal';target.write_bytes(b'private');p.symlink_to(target)
    with pytest.raises(ValueError,match='symlink'):m.fetch(a,tmp_path,Opener(b'good'))
    assert target.read_bytes()==b'private'

@pytest.mark.parametrize('url',['http://download.microsoft.com/a','https://download.microsoft.com.evil.test/a','https://evil.test/a','https://user@download.microsoft.com/a'])
def test_redirect_and_source_restrictions(url):
    with pytest.raises(ValueError):m.check_url(url)
    with pytest.raises(ValueError):m.OfficialRedirect().redirect_request(None,None,302,'',{},url)


def test_file_created_during_download_is_not_overwritten(tmp_path):
    class RacingOpener(Opener):
        def open(self, *args, **kwargs):
            (tmp_path/'test.exe').write_bytes(b'new user file')
            return super().open(*args, **kwargs)
    with pytest.raises(FileExistsError):m.fetch(asset(b'good'),tmp_path,RacingOpener(b'good'))
    assert (tmp_path/'test.exe').read_bytes()==b'new user file'
    assert len(list(tmp_path.iterdir()))==1


def test_predictable_partial_symlink_is_never_followed(tmp_path):
    target=tmp_path/'personal';target.write_bytes(b'private')
    class RacingOpener(Opener):
        def open(self,*args,**kwargs):
            (tmp_path/'test.exe.part').symlink_to(target)
            return super().open(*args,**kwargs)
    assert m.fetch(asset(b'good'),tmp_path,RacingOpener(b'good'))=='downloaded_verified'
    assert target.read_bytes()==b'private'

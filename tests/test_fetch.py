"""Tests for TTML, Enhanced LRC, LRC and plain-text fallback."""
from __future__ import annotations
import sys, types, unittest
from enum import Enum
from unittest.mock import patch
from gamdl_lyrics_retagger.update import fetch_best_lyrics

class Fmt(str,Enum):
    LRC="lrc"; ENHANCED_LRC="enhanced-lrc"; TEXT="text"
class Seg:
    def __init__(self,text,start): self.text=text; self.start=start
class Line:
    def __init__(self,text,start,segments=None): self.text=text; self.start=start; self.segments=segments or []
class Lyrics:
    def __init__(self,lines,plain=None,lrc="[00:00.50]Timed",enh="[00:00.50]<00:00.50>Timed"):
        self.lines=lines; self.plain=plain if plain is not None else "\n".join(x.text for x in lines)
        self.lrc=lrc; self.enh=enh; self.formats=[]
    def render(self,fmt,*,embedded):
        if embedded: raise AssertionError("Strict rendering expected")
        self.formats.append(fmt.value)
        return {Fmt.LRC:self.lrc,Fmt.ENHANCED_LRC:self.enh,Fmt.TEXT:self.plain}[fmt]
class SongInst:
    def __init__(self,standard,syllable=None,metadata=None):
        self.standard=standard; self.syllable=syllable
        self.metadata=metadata or {"attributes":{"name":"Test","artistName":"Artist","isrc":"USAAA0000001","hasLyrics":True}}
        self.calls=[]
    async def get_metadata(self): return self.metadata
    async def get_lyrics(self,**kwargs):
        self.calls.append(kwargs.copy()); return self.syllable if kwargs.get("syllable") else self.standard
class Song:
    instance=None
    @classmethod
    def from_id(cls,song_id,*,api,is_library): return cls.instance

class FetchTests(unittest.IsolatedAsyncioTestCase):
    def patch_gamdl(self):
        g=types.ModuleType("gamdl"); m=types.ModuleType("gamdl.media")
        s=types.ModuleType("gamdl.media.song"); l=types.ModuleType("gamdl.media.song.lyrics")
        m.Song=Song; l.LyricsFormat=Fmt; g.media=m; m.song=s; s.lyrics=l
        return patch.dict(sys.modules,{"gamdl":g,"gamdl.media":m,"gamdl.media.song":s,"gamdl.media.song.lyrics":l})
    async def test_standard_ttml_line_lrc(self):
        api=types.SimpleNamespace(language="es-MX",_lyrics_retagger_responses={})
        obj=Lyrics([Line("A",100),Line("B",200)])
        Song.instance=SongInst(obj)
        with self.patch_gamdl(): result=await fetch_best_lyrics(api,"10")
        self.assertEqual((result.endpoint,result.format),("standard","lrc"))
        self.assertEqual(obj.formats,["lrc"])
        self.assertEqual(Song.instance.calls,[{"syllable":False,"language":"es-MX"}])
    async def test_standard_ttml_enhanced_lrc(self):
        api=types.SimpleNamespace(language="en-US",_lyrics_retagger_responses={})
        obj=Lyrics([Line("hello",100,[Seg("he",100),Seg("llo",150)])])
        Song.instance=SongInst(obj)
        with self.patch_gamdl(): result=await fetch_best_lyrics(api,"10")
        self.assertEqual((result.endpoint,result.format),("standard","enhanced-lrc"))
    async def test_syllable_enhanced_lrc(self):
        api=types.SimpleNamespace(language="en-US",_lyrics_retagger_responses={})
        standard=Lyrics([Line("untimed",None)])
        syll=Lyrics([Line("hello",100,[Seg("he",100),Seg("llo",150)])])
        Song.instance=SongInst(standard,syll)
        with self.patch_gamdl(): result=await fetch_best_lyrics(api,"10")
        self.assertEqual((result.endpoint,result.format),("syllable","enhanced-lrc"))
        self.assertEqual(len(Song.instance.calls),2)
    async def test_syllable_line_lrc(self):
        api=types.SimpleNamespace(language="en-US",_lyrics_retagger_responses={})
        standard=Lyrics([Line("untimed",None)])
        syll=Lyrics([Line("timed",500)],lrc="[00:00.50]timed")
        Song.instance=SongInst(standard,syll)
        with self.patch_gamdl(): result=await fetch_best_lyrics(api,"10")
        self.assertEqual((result.endpoint,result.format),("syllable","lrc"))
    async def test_text_fallback_standard(self):
        api=types.SimpleNamespace(language="en-US",_lyrics_retagger_responses={})
        standard=Lyrics([Line("A",None),Line("B",None)],plain="A\nB")
        syll=Lyrics([Line("C",None)])
        Song.instance=SongInst(standard,syll)
        with self.patch_gamdl(): result=await fetch_best_lyrics(api,"10")
        self.assertEqual((result.endpoint,result.format,result.text),("standard","text","A\nB"))
        self.assertEqual(standard.formats,["text"])
    async def test_text_fallback_syllable(self):
        api=types.SimpleNamespace(language="en-US",_lyrics_retagger_responses={})
        syll=Lyrics([Line("Only text",None)])
        Song.instance=SongInst(None,syll)
        with self.patch_gamdl(): result=await fetch_best_lyrics(api,"10")
        self.assertEqual((result.endpoint,result.format),("syllable","text"))
    async def test_no_content(self):
        api=types.SimpleNamespace(language="en-US",_lyrics_retagger_responses={})
        Song.instance=SongInst(None)
        with self.patch_gamdl(): result=await fetch_best_lyrics(api,"10")
        self.assertIsNone(result); self.assertEqual(len(Song.instance.calls),2)
    async def test_catalog_has_no_lyrics(self):
        api=types.SimpleNamespace(language="en-US",_lyrics_retagger_responses={})
        Song.instance=SongInst(Lyrics([Line("A",1)]),metadata={"attributes":{"hasLyrics":False}})
        with self.patch_gamdl(): result=await fetch_best_lyrics(api,"10")
        self.assertIsNone(result); self.assertEqual(Song.instance.calls,[])
if __name__=="__main__": unittest.main()

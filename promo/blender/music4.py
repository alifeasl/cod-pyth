"""Playful kids track: marimba melody, ukulele-ish plucks, claps, shaker,
boings on jumps and pops on speech bubbles. Usage: python3 music4.py out.wav"""
import sys, wave
import numpy as np
SR=44100; DUR=21.0; BPM=116; BEAT=60/BPM
POPS=[0.3,2.7,5.3,6.4,8.4,13.4,15.2,17.3,17.9]
BOINGS=[6.35,6.85,11.7,11.85]+[17.5+i*(np.pi/5.2) for i in range(6)]
IRIS=[8.0,12.5,17.0]
n=int(SR*DUR); t=np.arange(n)/SR; mix=np.zeros(n); rng=np.random.default_rng(9)
def add(sig,at,g=1.0):
    i=int(at*SR); j=min(n,i+len(sig))
    if 0<=i<n: mix[i:j]+=sig[:j-i]*g
tt=lambda s: np.arange(int(s*SR))/SR
m=lambda k:440*2**((k-69)/12)
def marimba(f,l=.6):
    x=tt(l); return (np.sin(2*np.pi*f*x)+.3*np.sin(2*np.pi*f*4*x)*np.exp(-x*30))*np.exp(-x*7)*np.minimum(x/.002,1)
def pluck(f,l=.5):
    x=tt(l); s=sum(np.sin(2*np.pi*f*h*x)/h for h in (1,2,3,4))
    return s*np.exp(-x*6)*np.minimum(x/.003,1)*.6
def bass(f,l):
    x=tt(l); return np.sin(2*np.pi*f*x)*np.exp(-x*3)*np.minimum(x/.01,1)
def kick():
    x=tt(.25); return np.sin(2*np.pi*np.cumsum(50+100*np.exp(-x*40))/SR)*np.exp(-x*12)
def clap():
    x=tt(.18); nz=np.diff(rng.standard_normal(len(x)),prepend=0)
    e=np.exp(-x*30)+.5*np.exp(-np.maximum(x-.012,0)*30)*(x>.012); return nz*e*.3
def shaker():
    x=tt(.07); return np.diff(rng.standard_normal(len(x)),prepend=0)*np.sin(np.pi*x/.07)*.08
def boing():
    x=tt(.35); f=220+260*np.sin(x*18)*np.exp(-x*6)+x*300
    return np.sin(2*np.pi*np.cumsum(f)/SR)*np.exp(-x*7)*.6
def pop():
    x=tt(.09); return np.sin(2*np.pi*np.cumsum(500+1800*x/.09)/SR)*np.exp(-x*40)
def swish():
    x=tt(.6); f=300+1500*(x/.6); return np.sin(2*np.pi*np.cumsum(f)/SR)*np.sin(np.pi*x/.6)**2*.25
CH=[[60,64,67],[65,69,72],[67,71,74],[60,64,67]]   # C F G C
BS=[48,41,43,48]
MEL=[72,74,76,79, 77,76,74,72, 74,76,77,76, 74,72,71,72,
     76,79,81,79, 77,76,74,76, 79,77,76,74, 72,74,72,None]
beats=int(DUR/BEAT)
for b in range(beats):
    at=b*BEAT; bar=(b//4)%4
    end=at>DUR-1.2
    if end: break
    if b%4==0: add(bass(m(BS[bar]),BEAT*2),at,.35)
    if b%4==2: add(bass(m(BS[bar]+7),BEAT*2),at,.25)
    add(kick(),at,.55 if b%2==0 else .3)
    if b%2==1: add(clap(),at,.9)
    for k in range(2): add(shaker(),at+k*BEAT/2,1)
    # plucked chord offbeats
    for k in CH[bar]: add(pluck(m(k)),at+BEAT/2,.09)
    # melody in 8ths-ish (one note per beat, doubled in last section)
    note=MEL[b%len(MEL)]
    if note and at>.2: add(marimba(m(note)),at,.28)
    if at>21 and note: add(marimba(m(note+12)),at+BEAT/2,.14)
for p in POPS: add(pop(),p,.25)
for b in BOINGS: add(boing(),b,.35)
for s in IRIS: add(swish(),s-.45,1)
# final chime
for i,k in enumerate([72,76,79,84]): add(marimba(m(k),1.2),DUR-1.4+i*.08,.25)
fade=np.clip((DUR-t)/.6,0,1)*np.clip(t/.05,0,1); mix*=fade
mix=np.tanh(mix*1.1); mix/=np.max(np.abs(mix))+1e-9; mix*=.88
st=np.stack([mix,np.roll(mix,70)],axis=1)
with wave.open(sys.argv[1],'wb') as w:
    w.setnchannels(2);w.setsampwidth(2);w.setframerate(SR);w.writeframes((st*32767).astype(np.int16).tobytes())
print('wrote',sys.argv[1])

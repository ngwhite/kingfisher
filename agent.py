#!/usr/bin/env python3
"""
Chess AI Advisor
────────────────
Paste your move list (one move per line, or space-separated) and get
the best next move instantly.

Accepted formats — any of these work:
    e4          (just the move)
    1. e4       (with move number)
    1. e4 e5    (both sides on one line)

Requirements:  pip install pillow
Run:           python chess_advisor_v2.py
"""

import math, time, threading, re
import tkinter as tk
from PIL import Image, ImageDraw, ImageTk

# ══════════════════════════════════════════════════════════════════════════════
#  CHESS ENGINE
# ══════════════════════════════════════════════════════════════════════════════

INITIAL_BOARD = [
    'r','n','b','q','k','b','n','r',
    'p','p','p','p','p','p','p','p',
    *([None]*32),
    'P','P','P','P','P','P','P','P',
    'R','N','B','Q','K','B','N','R',
]

FILES = 'abcdefgh'
def _r(i):    return i // 8
def _c(i):    return i % 8
def _sq(r,c): return r*8+c
def _ib(r,c): return 0<=r<8 and 0<=c<8
def _iw(p):   return p is not None and p.isupper()
def _sc(a,b): return a and b and (_iw(a)==_iw(b))
def sq_name(i): return FILES[_c(i)] + str(8-_r(i))
def name_sq(s): return _sq(8-int(s[1]), FILES.index(s[0]))

SLIDERS = {
    'B':[(-1,-1),(-1,1),(1,-1),(1,1)],
    'R':[(-1,0),(1,0),(0,-1),(0,1)],
    'Q':[(-1,-1),(-1,1),(1,-1),(1,1),(-1,0),(1,0),(0,-1),(0,1)],
}

def pseudo_moves(board, frm, ep, cr):
    p = board[frm]
    if not p: return []
    r,c = _r(frm),_c(frm); white=_iw(p); moves=[]
    def add(to,sp=None):
        if _ib(_r(to),_c(to)): moves.append({'from':frm,'to':to,'special':sp,'piece':p})
    pt=p.upper()
    if pt=='P':
        d=-1 if white else 1; sr=6 if white else 1; pr=0 if white else 7
        fwd=_sq(r+d,c)
        if not board[fwd]:
            add(fwd,'promo' if _r(fwd)==pr else None)
            if r==sr and not board[_sq(r+2*d,c)]: add(_sq(r+2*d,c),'dp')
        for dc in(-1,1):
            if _ib(r+d,c+dc):
                t=_sq(r+d,c+dc)
                if board[t] and not _sc(p,board[t]): add(t,'promo' if _r(t)==pr else None)
                if ep==t: add(t,'ep')
    elif pt=='N':
        for dr,dc in[(-2,-1),(-2,1),(-1,-2),(-1,2),(1,-2),(1,2),(2,-1),(2,1)]:
            if _ib(r+dr,c+dc):
                t=_sq(r+dr,c+dc)
                if not _sc(p,board[t]): add(t)
    elif pt=='K':
        for dr,dc in[(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]:
            if _ib(r+dr,c+dc):
                t=_sq(r+dr,c+dc)
                if not _sc(p,board[t]): add(t)
        if cr:
            if white:
                if cr.get('wK') and not board[61] and not board[62] and board[63]=='R': add(62,'castle-k')
                if cr.get('wQ') and not board[59] and not board[58] and not board[57] and board[56]=='R': add(58,'castle-q')
            else:
                if cr.get('bK') and not board[5] and not board[6] and board[7]=='r': add(6,'castle-k')
                if cr.get('bQ') and not board[3] and not board[2] and not board[1] and board[0]=='r': add(2,'castle-q')
    else:
        for dr,dc in SLIDERS.get(pt,[]):
            nr,nc=r+dr,c+dc
            while _ib(nr,nc):
                t=_sq(nr,nc)
                if _sc(p,board[t]): break
                add(t)
                if board[t]: break
                nr+=dr; nc+=dc
    return moves

def apply_move(board,mv,cr,ep):
    nb=list(board); ncr=dict(cr); nep=None
    p=nb[mv['from']]; nb[mv['to']]=p; nb[mv['from']]=None
    sp=mv.get('special')
    if sp=='ep':    nb[_sq(_r(mv['from']),_c(mv['to']))]=None
    if sp=='dp':    nep=_sq(_r(mv['from'])+(_r(mv['to'])-_r(mv['from']))//2,_c(mv['from']))
    if sp=='promo': nb[mv['to']]=(mv.get('promo_piece','Q') if _iw(p) else mv.get('promo_piece','Q').lower())
    if sp=='castle-k':
        if _iw(p): nb[61]='R';nb[63]=None
        else:      nb[5]='r';nb[7]=None
    if sp=='castle-q':
        if _iw(p): nb[59]='R';nb[56]=None
        else:      nb[3]='r';nb[0]=None
    if p=='K': ncr['wK']=ncr['wQ']=False
    if p=='k': ncr['bK']=ncr['bQ']=False
    for si,k in[(63,'wK'),(56,'wQ'),(7,'bK'),(0,'bQ')]:
        if mv['from']==si or mv['to']==si: ncr[k]=False
    return nb,ncr,nep

def in_check(board,white):
    king='K' if white else 'k'
    try: ki=board.index(king)
    except ValueError: return True
    for i,p in enumerate(board):
        if not p or (_iw(p)==white): continue
        if any(m['to']==ki for m in pseudo_moves(board,i,None,None)): return True
    return False

def legal_moves(board,white,ep,cr):
    out=[]
    for i,p in enumerate(board):
        if not p or (_iw(p)!=white): continue
        for mv in pseudo_moves(board,i,ep,cr):
            nb,ncr,nep=apply_move(board,mv,cr,ep)
            if not in_check(nb,white): out.append(mv)
    return out

_STRIP=re.compile(r'[+#!?x]')

def parse_san(tok, board, white, ep, cr):
    tok=_STRIP.sub('',tok).strip()
    if tok in('O-O','0-0','o-o'):
        t=62 if white else 6
        for mv in legal_moves(board,white,ep,cr):
            if mv['to']==t and mv.get('special')=='castle-k': return mv
        raise ValueError("Kingside castling not legal")
    if tok in('O-O-O','0-0-0','o-o-o'):
        t=58 if white else 2
        for mv in legal_moves(board,white,ep,cr):
            if mv['to']==t and mv.get('special')=='castle-q': return mv
        raise ValueError("Queenside castling not legal")
    promo=None
    pm=re.search(r'=?([QRBN])$',tok)
    if pm: promo=pm.group(1); tok=tok[:pm.start()]
    if len(tok)<2: raise ValueError(f"Too short: {tok}")
    dest_str=tok[-2:]
    if dest_str[0] not in FILES or dest_str[1] not in '12345678':
        raise ValueError(f"Bad destination: {dest_str}")
    dest=name_sq(dest_str)
    rem=tok[:-2]
    if rem and rem[0].isupper(): pt=rem[0]; dis=rem[1:]
    else: pt='P'; dis=rem
    df=dr=None
    for ch in dis:
        if ch in FILES: df=FILES.index(ch)
        elif ch.isdigit(): dr=8-int(ch)
    cands=[]
    for mv in legal_moves(board,white,ep,cr):
        p=board[mv['from']]
        if not p or p.upper()!=pt or mv['to']!=dest: continue
        if df is not None and _c(mv['from'])!=df: continue
        if dr is not None and _r(mv['from'])!=dr: continue
        cands.append(mv)
    if not cands: raise ValueError(f"No legal move: {tok}")
    if len(cands)>1: raise ValueError(f"Ambiguous: {tok}")
    mv=cands[0]
    if promo: mv=dict(mv,promo_piece=promo,special='promo')
    return mv

# Piece-square tables & eval
PIECE_VALUES={'P':100,'N':320,'B':330,'R':500,'Q':900,'K':20000,'p':-100,'n':-320,'b':-330,'r':-500,'q':-900,'k':-20000}
PAWN_T  =[0,0,0,0,0,0,0,0,50,50,50,50,50,50,50,50,10,10,20,30,30,20,10,10,5,5,10,25,25,10,5,5,0,0,0,20,20,0,0,0,5,-5,-10,0,0,-10,-5,5,5,10,10,-20,-20,10,10,5,0,0,0,0,0,0,0,0]
KNIGHT_T=[-50,-40,-30,-30,-30,-30,-40,-50,-40,-20,0,0,0,0,-20,-40,-30,0,10,15,15,10,0,-30,-30,5,15,20,20,15,5,-30,-30,0,15,20,20,15,0,-30,-30,5,10,15,15,10,5,-30,-40,-20,0,5,5,0,-20,-40,-50,-40,-30,-30,-30,-30,-40,-50]
BISHOP_T=[-20,-10,-10,-10,-10,-10,-10,-20,-10,0,0,0,0,0,0,-10,-10,0,5,10,10,5,0,-10,-10,5,5,10,10,5,5,-10,-10,0,10,10,10,10,0,-10,-10,10,10,10,10,10,10,-10,-10,5,0,0,0,0,5,-10,-20,-10,-10,-10,-10,-10,-10,-20]
ROOK_T  =[0,0,0,0,0,0,0,0,5,10,10,10,10,10,10,5,-5,0,0,0,0,0,0,-5,-5,0,0,0,0,0,0,-5,-5,0,0,0,0,0,0,-5,-5,0,0,0,0,0,0,-5,-5,0,0,0,0,0,0,-5,0,0,0,5,5,0,0,0]
QUEEN_T =[-20,-10,-10,-5,-5,-10,-10,-20,-10,0,0,0,0,0,0,-10,-10,0,5,5,5,5,0,-10,-5,0,5,5,5,5,0,-5,0,0,5,5,5,5,0,-5,-10,5,5,5,5,5,0,-10,-10,0,5,0,0,0,0,-10,-20,-10,-10,-5,-5,-10,-10,-20]
KING_T  =[-30,-40,-40,-50,-50,-40,-40,-30,-30,-40,-40,-50,-50,-40,-40,-30,-30,-40,-40,-50,-50,-40,-40,-30,-30,-40,-40,-50,-50,-40,-40,-30,-20,-30,-30,-40,-40,-30,-30,-20,-10,-20,-20,-20,-20,-20,-20,-10,20,20,0,0,0,0,20,20,20,30,10,0,0,10,30,20]
PST={'P':PAWN_T,'N':KNIGHT_T,'B':BISHOP_T,'R':ROOK_T,'Q':QUEEN_T,'K':KING_T}

def _pst(p,i):
    tbl=PST.get(p.upper())
    return tbl[i if _iw(p) else 63-i] if tbl else 0

def _eval(board):
    return sum(PIECE_VALUES[p]+_pst(p,i)*(1 if _iw(p) else -1) for i,p in enumerate(board) if p)

def _minimax(board,depth,alpha,beta,maxi,ep,cr):
    if depth==0: return _eval(board),None
    moves=legal_moves(board,maxi,ep,cr)
    if not moves: return((-99999 if maxi else 99999) if in_check(board,maxi) else 0),None
    best=float('-inf') if maxi else float('inf'); bm=None
    for mv in moves:
        nb,ncr,nep=apply_move(board,mv,cr,ep)
        sc,_=_minimax(nb,depth-1,alpha,beta,not maxi,nep,ncr)
        if maxi:
            if sc>best: best,bm=sc,mv
            alpha=max(alpha,best)
        else:
            if sc<best: best,bm=sc,mv
            beta=min(beta,best)
        if beta<=alpha: break
    return best,bm

def find_best_move(board,white,ep,cr,depth=3):
    t0=time.time()
    sc,mv=_minimax(board,depth,float('-inf'),float('inf'),white,ep,cr)
    return mv,sc,time.time()-t0

def mv_name(mv):
    if not mv: return '—'
    return sq_name(mv['from'])+sq_name(mv['to'])+('=Q' if mv.get('special')=='promo' else '')

# ══════════════════════════════════════════════════════════════════════════════
#  GAME STATE
# ══════════════════════════════════════════════════════════════════════════════

class GameState:
    def __init__(self): self.reset()

    def reset(self):
        self.board=list(INITIAL_BOARD)
        self.castling={'wK':True,'wQ':True,'bK':True,'bQ':True}
        self.ep=None; self.white=True
        self.moves=[]; self.last_mv=None; self.error=None

    def apply_san(self,token):
        token=token.strip()
        if not token: return True
        try:
            mv=parse_san(token,self.board,self.white,self.ep,self.castling)
        except ValueError as e:
            self.error=str(e); return False
        self.board,self.castling,self.ep=apply_move(self.board,mv,self.castling,self.ep)
        self.white=not self.white; self.moves.append(token)
        self.last_mv=mv; self.error=None; return True

    def load_moves(self, text):
        """
        Accepts moves one-per-line, space-separated, or numbered PGN format.
        Lines like:  e4  /  1. e4  /  1. e4 e5  /  e4 e5 Nf3
        """
        self.reset()
        tokens=[]
        for line in text.splitlines():
            line=line.strip()
            if not line: continue
            line=re.sub(r'\b\d+\.+\s*','',line)          # strip move numbers
            line=re.sub(r'\b(1-0|0-1|1/2-1/2|\*)\b','',line)  # strip results
            tokens.extend(line.split())
        for tok in tokens:
            tok=tok.strip()
            if not tok: continue
            if not self.apply_san(tok):
                return len(self.moves), tok
        return len(self.moves), None

    def side_to_move(self): return 'White' if self.white else 'Black'
    def move_number(self):  return len(self.moves)//2+1

# ══════════════════════════════════════════════════════════════════════════════
#  BOARD RENDERER
# ══════════════════════════════════════════════════════════════════════════════

LIGHT_SQ=(240,217,181); DARK_SQ=(181,136,99)
GLYPHS={'K':'♔','Q':'♕','R':'♖','B':'♗','N':'♘','P':'♙',
        'k':'♚','q':'♛','r':'♜','b':'♝','n':'♞','p':'♟'}

_fcache={}
def _pfont(size):
    if size not in _fcache:
        from PIL import ImageFont
        for name in['seguisym.ttf','NotoSans-Regular.ttf','DejaVuSans.ttf','arial.ttf']:
            try: _fcache[size]=ImageFont.truetype(name,size); break
            except OSError: pass
        else: _fcache[size]=ImageFont.load_default()
    return _fcache[size]

def render_board(board,px=320,last_mv=None,best_mv=None,flip=False):
    sq=px//8; img=Image.new('RGB',(px,px)); draw=ImageDraw.Draw(img,'RGBA')
    hl={last_mv['from'],last_mv['to']} if last_mv else set()
    for idx in range(64):
        ri,ci=_r(idx),_c(idx)
        if flip: ri,ci=7-ri,7-ci
        x0,y0=ci*sq,ri*sq
        light=(ri+ci)%2==0; base=LIGHT_SQ if light else DARK_SQ
        if idx in hl:
            r2,g2,b2=base; base=(min(255,r2+25),min(255,g2+25),max(0,b2-15))
        draw.rectangle([x0,y0,x0+sq-1,y0+sq-1],fill=base)
        p=board[idx]
        if p:
            ch=GLYPHS.get(p,p)
            fg=(255,255,255) if _iw(p) else (25,15,5)
            ol=(25,15,5)     if _iw(p) else (215,195,160)
            fs=int(sq*0.70); tx,ty=x0+sq//2,y0+sq//2; f=_pfont(fs)
            for dx,dy in[(-2,0),(2,0),(0,-2),(0,2),(-1,-1),(1,1),(-1,1),(1,-1)]:
                draw.text((tx+dx,ty+dy),ch,fill=ol,anchor='mm',font=f)
            draw.text((tx,ty),ch,fill=fg,anchor='mm',font=f)
    if best_mv:
        def ctr(i):
            ri2,ci2=_r(i),_c(i)
            if flip: ri2,ci2=7-ri2,7-ci2
            return ci2*sq+sq//2,ri2*sq+sq//2
        x1,y1=ctr(best_mv['from']); x2,y2=ctr(best_mv['to'])
        draw.line([(x1,y1),(x2,y2)],fill=(220,50,50,200),width=max(4,sq//8))
        ang=math.atan2(y2-y1,x2-x1); tl=sq//4
        for da in(2.4,-2.4):
            ax=x2-tl*math.cos(ang+da); ay=y2-tl*math.sin(ang+da)
            draw.line([(x2,y2),(int(ax),int(ay))],fill=(220,50,50,200),width=max(3,sq//10))
    lc=(160,160,160); lf=_pfont(max(8,sq//6))
    for i in range(8):
        ci2=7-i if flip else i
        draw.text((ci2*sq+sq//2,px-max(8,sq//6)-1),FILES[i],fill=lc,anchor='mt',font=lf)
        ri2=i if flip else 7-i
        draw.text((2,ri2*sq+2),str(i+1 if flip else 8-i),fill=lc,anchor='lt',font=lf)
    return img

# ══════════════════════════════════════════════════════════════════════════════
#  GUI
# ══════════════════════════════════════════════════════════════════════════════

BG='#1a1a2e'; BG2='#252540'; BG3='#0f0f1e'
GOLD='#e2b96f'; FG='#e8e0d0'; FAINT='#888888'; ERR='#e05555'; OK='#5cb87a'
BOARD_PX=320

class App:
    def __init__(self):
        self.root=tk.Tk()
        self.root.title('Chess AI Advisor')
        self.root.configure(bg=BG)
        self.root.resizable(True,True)
        self.root.minsize(720,560)
        self.game=GameState()
        self.depth_var=tk.IntVar(value=3)
        self._bref=None; self._best_mv=None; self._busy=False
        self._build()
        self._redraw()
        self.root.mainloop()

    def _build(self):
        root=self.root

        # ── toolbar ──
        tb=tk.Frame(root,bg=BG,pady=10); tb.pack(fill='x',padx=16)
        tk.Label(tb,text='♟  Chess AI Advisor',font=('Georgia',16,'bold'),bg=BG,fg=GOLD).pack(side='left')
        df=tk.Frame(tb,bg=BG); df.pack(side='right')
        tk.Label(df,text='Depth',bg=BG,fg=FAINT,font=('Courier',9)).pack(side='left',padx=(0,4))
        self._dlbl=tk.Label(df,text='3',bg=BG,fg=GOLD,font=('Courier',11,'bold'),width=2); self._dlbl.pack(side='right')
        tk.Scale(df,from_=1,to=5,orient='horizontal',variable=self.depth_var,
                 command=lambda v:self._dlbl.config(text=v),
                 bg=BG,fg=FG,troughcolor=BG2,highlightthickness=0,
                 sliderrelief='flat',length=100,showvalue=False).pack(side='left')

        tk.Frame(root,bg='#2a2a45',height=1).pack(fill='x')

        # ── two columns ──
        main=tk.Frame(root,bg=BG); main.pack(fill='both',expand=True)
        main.columnconfigure(0,weight=1); main.columnconfigure(1,weight=0)

        # LEFT — input
        left=tk.Frame(main,bg=BG,padx=14,pady=12)
        left.grid(row=0,column=0,sticky='nsew')
        left.rowconfigure(1,weight=1); left.columnconfigure(0,weight=1)

        tk.Label(left,text='Paste moves here — one move per line:',
                 bg=BG,fg=FG,font=('Georgia',10),anchor='w').grid(row=0,column=0,sticky='ew',pady=(0,4))

        # hint label
        tk.Label(left,
                 text='Accepts: "e4", "1. e4", "1. e4 e5", or mixed formats',
                 bg=BG,fg=FAINT,font=('Courier',8),anchor='w').grid(row=0,column=0,sticky='sw')

        txt_wrap=tk.Frame(left,bg=BG2); txt_wrap.grid(row=1,column=0,sticky='nsew',pady=(18,0))
        self._txt=tk.Text(txt_wrap,bg=BG2,fg=FG,insertbackground=GOLD,
                          font=('Courier',12),relief='flat',padx=10,pady=8,
                          wrap='none',undo=True,width=26,
                          selectbackground=BG3,selectforeground=FG)
        sb=tk.Scrollbar(txt_wrap,command=self._txt.yview,bg=BG2,troughcolor=BG,relief='flat')
        self._txt.configure(yscrollcommand=sb.set)
        self._txt.pack(side='left',fill='both',expand=True)
        sb.pack(side='right',fill='y')
        self._txt.bind('<KeyRelease>',self._on_change)

        self._status=tk.Label(left,text='Paste your moves above',
                              bg=BG,fg=FAINT,font=('Courier',9),anchor='w')
        self._status.grid(row=2,column=0,sticky='ew',pady=(4,0))

        btns=tk.Frame(left,bg=BG,pady=8); btns.grid(row=3,column=0,sticky='ew')
        self._abtn=self._btn(btns,'🔍  Analyse',self._analyse,primary=True)
        self._abtn.pack(side='left',padx=(0,8))
        self._btn(btns,'↩  Undo last',self._undo).pack(side='left',padx=(0,8))
        self._btn(btns,'✕  Clear',self._clear).pack(side='left')

        # RIGHT — board + result
        right=tk.Frame(main,bg=BG3); right.grid(row=0,column=1,sticky='nsew')

        self._canvas=tk.Canvas(right,width=BOARD_PX,height=BOARD_PX,
                               highlightthickness=0,bg='#111')
        self._canvas.pack()

        self._side_var=tk.StringVar(value='White to move')
        tk.Label(right,textvariable=self._side_var,bg=BG3,fg=FAINT,
                 font=('Courier',9)).pack(fill='x',padx=10,pady=(2,0))

        tk.Frame(right,bg='#2a2a45',height=1).pack(fill='x',pady=4)

        res=tk.Frame(right,bg=BG3,padx=14,pady=8); res.pack(fill='x')
        tk.Label(res,text='BEST MOVE',bg=BG3,fg=FAINT,font=('Courier',8),anchor='w').pack(fill='x')
        self._move_var=tk.StringVar(value='—')
        tk.Label(res,textvariable=self._move_var,bg=BG3,fg=GOLD,
                 font=('Georgia',32,'bold'),anchor='w').pack(fill='x')
        self._eval_var=tk.StringVar(value='')
        tk.Label(res,textvariable=self._eval_var,bg=BG3,fg=FAINT,
                 font=('Courier',9),anchor='w').pack(fill='x')
        self._think_var=tk.StringVar(value='')
        tk.Label(res,textvariable=self._think_var,bg=BG3,fg=FAINT,
                 font=('Courier',9,'italic'),anchor='w').pack(fill='x')

        self._fen_var=tk.StringVar(value='')
        tk.Label(right,textvariable=self._fen_var,bg=BG3,fg='#3a3a5a',
                 font=('Courier',7),wraplength=BOARD_PX-8,
                 anchor='w',justify='left').pack(fill='x',padx=6,pady=(4,8))

    def _btn(self,parent,text,cmd,primary=False):
        bg=GOLD if primary else BG2; fg=BG if primary else GOLD
        return tk.Button(parent,text=text,command=cmd,
                         font=('Georgia',10,'bold' if primary else 'normal'),
                         bg=bg,fg=fg,activebackground=bg,activeforeground=fg,
                         relief='flat',padx=12,pady=7,cursor='hand2')

    def _on_change(self,event=None):
        text=self._txt.get('1.0','end').strip()
        self._best_mv=None; self._move_var.set('—'); self._eval_var.set(''); self._think_var.set('')
        if not text:
            self.game.reset()
            self._status.config(text='Paste your moves above',fg=FAINT)
            self._redraw(); return
        n,err=self.game.load_moves(text)
        if err:
            self._status.config(text=f'⚠  Unrecognised move: "{err}"',fg=ERR)
        else:
            self._status.config(
                text=f'✓  {n} move{"s" if n!=1 else ""}  ·  move {self.game.move_number()}  ·  {self.game.side_to_move()} to move',
                fg=OK)
        self._redraw()

    def _redraw(self,best_mv=None):
        flip=not self.game.white
        img=render_board(self.game.board,px=BOARD_PX,last_mv=self.game.last_mv,
                         best_mv=best_mv or self._best_mv,flip=flip)
        self._bref=ImageTk.PhotoImage(img)
        self._canvas.delete('all'); self._canvas.create_image(0,0,anchor='nw',image=self._bref)
        nm=len(self.game.moves)
        self._side_var.set(
            f"{'White' if self.game.white else 'Black'} to move"
            +(f'  ·  move {self.game.move_number()}' if nm else ''))

    def _analyse(self):
        self._on_change()
        if self.game.error or self._busy: return
        lm=legal_moves(self.game.board,self.game.white,self.game.ep,self.game.castling)
        if not lm:
            self._move_var.set('Checkmate' if in_check(self.game.board,self.game.white) else 'Stalemate')
            self._eval_var.set(''); return
        self._busy=True; self._abtn.config(state='disabled')
        self._move_var.set('…'); self._think_var.set('Thinking…')
        threading.Thread(target=self._worker,daemon=True).start()

    def _worker(self):
        try:
            d=self.depth_var.get()
            mv,sc,t=find_best_move(self.game.board,self.game.white,self.game.ep,self.game.castling,d)
            self.root.after(0,self._show,mv,sc,t,d)
        except Exception as e:
            self.root.after(0,self._err_show,str(e))

    def _show(self,mv,sc,t,d):
        self._busy=False; self._abtn.config(state='normal'); self._think_var.set('')
        if not mv: self._move_var.set('—'); return
        self._best_mv=mv; self._move_var.set(mv_name(mv))
        sign='+' if sc>0 else ''
        self._eval_var.set(f'eval {sign}{sc}  ·  depth {d}  ·  {t:.1f}s')
        # build FEN
        b=self.game.board; cr=self.game.castling; ep=self.game.ep; w=self.game.white
        parts=[]
        for row in range(8):
            e=0;s=''
            for col in range(8):
                p=b[row*8+col]
                if p:
                    if e: s+=str(e);e=0
                    s+=p
                else: e+=1
            if e: s+=str(e)
            parts.append(s)
        crs=''.join(ch for k,ch in[('wK','K'),('wQ','Q'),('bK','k'),('bQ','q')] if cr.get(k)) or '-'
        self._fen_var.set('/'.join(parts)+f" {'w' if w else 'b'} {crs} {sq_name(ep) if ep else '-'} 0 {self.game.move_number()}")
        self._redraw(best_mv=mv)

    def _err_show(self,msg):
        self._busy=False; self._abtn.config(state='normal')
        self._think_var.set(f'Error: {msg}')

    def _undo(self):
        lines=self._txt.get('1.0','end').rstrip('\n').splitlines()
        for i in range(len(lines)-1,-1,-1):
            clean=re.sub(r'\b\d+\.+\s*','',lines[i].strip())
            toks=clean.split()
            if toks:
                toks.pop()
                lines[i]=' '.join(toks) if toks else ''
                while lines and not lines[-1].strip(): lines.pop()
                break
        new='\n'.join(lines)
        self._txt.delete('1.0','end')
        if new.strip(): self._txt.insert('1.0',new)
        self._on_change()

    def _clear(self):
        self._txt.delete('1.0','end'); self._on_change()

if __name__=='__main__':
    App()

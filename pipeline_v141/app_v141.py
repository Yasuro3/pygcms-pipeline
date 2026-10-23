#!/usr/bin/env python3
"""Windows desktop launcher for PyGCMS Pipeline 1.4.1 (experimental NNLS).

The GUI runs the same audited CLI steps; it does not alter deconvolution or NIST
parameters in memory. Native NIST MS Search and its library are not bundled.
"""
from __future__ import annotations
import json, queue, subprocess, sys, threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

ROOT=Path(__file__).resolve().parent
PY=sys.executable

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('PyGCMS Pipeline 1.4.1 | Global NNLS (experimental)')
        self.minsize(860,640)
        self.source=tk.StringVar()
        self.phase=tk.StringVar(value='PY')
        self.manifest=tk.StringVar(value=str(ROOT/'samples'/'kobe_fa_40_manifest_LOCAL.json') if (ROOT/'samples'/'kobe_fa_40_manifest_LOCAL.json').exists() else '')
        self.events=queue.Queue();self.working=False
        top=ttk.Frame(self,padding=16);top.pack(fill='both',expand=True)
        ttk.Label(top,text='PyGCMS Pipeline v1.4.1',font=('Segoe UI',18,'bold')).pack(anchor='w')
        ttk.Label(top,text='Experimental global-NNLS deconvolution / released v1.4.0 NIST bridge and identification QC',foreground='#7a4c08').pack(anchor='w',pady=(0,12))
        ttk.Label(top,text='元mzML ZIP・フォルダー・.mzml（EGAはGC分離対象外）').pack(anchor='w')
        row=ttk.Frame(top);row.pack(fill='x',pady=(2,8));ttk.Entry(row,textvariable=self.source).pack(side='left',fill='x',expand=True)
        ttk.Button(row,text='ZIP/mzMLを選択',command=self.pick_source).pack(side='left',padx=(8,0))
        ttk.Button(row,text='フォルダーを選択',command=self.pick_directory).pack(side='left',padx=(5,0))
        ttk.Label(top,text='測定法（manifest未指定時）').pack(anchor='w')
        ttk.Combobox(top,textvariable=self.phase,values=['PY','TD','SS','EGA','GC_BLANK'],state='readonly',width=20).pack(anchor='w',pady=(0,8))
        ttk.Label(top,text='測定一覧 CSV / JSON（推奨：試料種とSS/TD/PY/EGAを明示）').pack(anchor='w')
        row=ttk.Frame(top);row.pack(fill='x',pady=(2,12));ttk.Entry(row,textvariable=self.manifest).pack(side='left',fill='x',expand=True)
        ttk.Button(row,text='測定一覧を選択',command=self.pick_manifest).pack(side='left',padx=(8,0))
        frame=ttk.Frame(top);frame.pack(fill='x',pady=(0,8))
        ops=[('1. mzML内容確認',self.preview),('2. 全mzMLを再分離',self.deconvolve),
             ('3. 数値テスト',self.tests),('4. NIST入力検証',self.validate),
             ('5. NIST設定',self.setup),('6. NIST全件検索',self.search),
             ('7. 途中から再開',self.resume),('8. 結果とQCを再集計',self.export),
             ('検索結果フォルダー',self.open_results)]
        for i,(label,fn) in enumerate(ops):
            btn=ttk.Button(frame,text=label,command=fn,width=24)
            btn.grid(row=i//3,column=i%3,padx=3,pady=4,sticky='ew')
        for i in range(3):frame.columnconfigure(i,weight=1)
        ttk.Label(top,text='進捗・監査ログ（NIST操作はWindows上のNIST MS Searchが必要です）').pack(anchor='w')
        view=ttk.Frame(top);view.pack(fill='both',expand=True)
        self.log=tk.Text(view,wrap='word',height=18,font=('Consolas',9))
        self.log.pack(side='left',fill='both',expand=True)
        scroll=ttk.Scrollbar(view,command=self.log.yview)
        scroll.pack(side='right',fill='y');self.log.configure(yscrollcommand=scroll.set)
        self.status=tk.StringVar(value='待機中。最初に Python 3.10+ / numpy / scipy をインストールしてください。')
        ttk.Label(top,textvariable=self.status).pack(anchor='w',pady=(8,0))
        self.after(100,self.drain)
    def pick_source(self):
        p=filedialog.askopenfilename(title='mzML ZIP or mzML file',filetypes=[('GCMS raw','*.zip *.mzML'),('All files','*.*')]);
        if p:self.source.set(p)
    def pick_directory(self):
        p=filedialog.askdirectory(title='Choose folder containing mzML');
        if p:self.source.set(p)
    def pick_manifest(self):
        p=filedialog.askopenfilename(filetypes=[('Manifest','*.json *.csv'),('All files','*.*')]);
        if p:self.manifest.set(p)
    def run_task(self,command,caption):
        if self.working:
            messagebox.showwarning('処理中','他の処理が終了するまでお待ちください。');return
        self.working=True;self.status.set(caption+' 実行中...');self.log.insert('end','\n>>> '+caption+'\n');self.log.see('end')
        def worker():
            try:
                p=subprocess.Popen([PY,*command],cwd=str(ROOT),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                                   text=True,encoding='utf-8',errors='replace',bufsize=1)
                for line in iter(p.stdout.readline,''):self.events.put(('line',line))
                self.events.put(('done',p.wait()))
            except Exception as exc:self.events.put(('error',str(exc)))
        threading.Thread(target=worker,daemon=True).start()
    def raw_args(self):
        raw=self.source.get().strip().strip('"')
        if not raw or not Path(raw).exists():
            messagebox.showerror('入力未指定','存在するmzMLファイル・ZIP・フォルダーを指定してください。');return None
        options=['engine/batch_v141.py','--input',raw,'--output',str(ROOT/'nist_search')]
        m=self.manifest.get().strip().strip('"')
        if m:
            if not Path(m).exists():messagebox.showerror('測定一覧なし','指定した測定一覧が存在しません。');return None
            options+=['--manifest',m]
        else:options+=['--phase',self.phase.get()]
        return options
    def preview(self):
        a=self.raw_args()
        if a:self.run_task(a+['--dry-run'],'mzML測定法・試料名確認')
    def deconvolve(self):
        a=self.raw_args()
        if not a:return
        if (ROOT/'nist_search'/'inputs'/'query_index.json').exists():
            messagebox.showerror('既存データ保護','検索入力がすでにあります。再解析時はまず配布フォルダー全体を別名で複製し、その複製の inputs と results を退避してください。既存のMS Search結果を混ぜません。');return
        if not messagebox.askyesno('再デコンボリューション','指定のmzMLから実験的NNLSで再解析します。品質は自動的に確定しません。続行しますか？'):
            return
        self.run_task(a,'Global NNLS再解析')
    def tests(self):self.run_task(['engine/test_global.py'],'数値・面積保存テスト')
    def validate(self):self.run_task(['nist_search/scripts/run_mssearch_v141.py','--validate-only','--scope','all'],'NIST入力の整合性検証')
    def setup(self):
        messagebox.showinfo('NIST設定','NIST設定は対話式です。GUIからはコマンドウィンドウを別に開いて実行してください。')
        script=ROOT/'03_CONFIGURE_NIST.cmd'
        if sys.platform=='win32':subprocess.Popen(['cmd.exe','/c',str(script)],cwd=str(ROOT),creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:messagebox.showerror('Windows専用','NIST MS SearchはWindowsでのみ動作します。')
    def search(self):
        if not messagebox.askyesno('NIST検索開始','NIST MS Searchが起動し、Automationとライブラリ設定を確認できていますか？\n検索中はNISTを手動操作しないでください。'):return
        self.run_task(['nist_search/scripts/run_mssearch_v141.py','--scope','all'],'全NISTスペクトル検索')
    def resume(self):
        if not messagebox.askyesno('再開の確認','NISTが完全に待機状態であることを確認しましたか？\n未完了の検索を再開します。'):return
        self.run_task(['nist_search/scripts/run_mssearch_v141.py','--scope','all','--resume-after-check'],'NIST中断分の再開')
    def export(self):self.run_task(['nist_search/scripts/run_mssearch_v141.py','--scope','all','--export-only'],'CSV・同定QCブラウザー再集計')
    def open_results(self):
        target=ROOT/'nist_search'/'results'/'all';target.mkdir(parents=True,exist_ok=True)
        if sys.platform=='win32':subprocess.Popen(['explorer.exe',str(target)])
        else:messagebox.showinfo('結果フォルダー',str(target))
    def drain(self):
        while True:
            try:kind,value=self.events.get_nowait()
            except queue.Empty:break
            if kind=='line':self.log.insert('end',value);self.log.see('end')
            else:
                self.working=False
                if kind=='error':self.status.set('ERROR: '+value);self.log.insert('end','ERROR: '+value+'\n')
                else:self.status.set('正常終了' if value==0 else f'終了コード {value}。ログを確認してください。')
        self.after(100,self.drain)

if __name__=='__main__':App().mainloop()

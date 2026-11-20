import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, numpy as np
S,I,I2,G="#fcfcfb","#0b0b0b","#52514e","#e4e3df"; F,L,O="#2a78d6","#86b6ef","#b4b2a9"
plt.rcParams.update({"font.family":"Segoe UI","font.size":10.5})
fig,(a,b)=plt.subplots(1,2,figsize=(12,4.6),dpi=150,gridspec_kw={"width_ratios":[1.6,1]})
fig.patch.set_facecolor(S)
m=["Sansamp Bass\nDriver 01","Darkglass Fuzz\nOMEGA","PP-DI-Only","B7K 6505+\nDistorted Bass"]
full=[130.5,134.1,135.3,125.8]; lite=[24.6,26.5,22.7,16.1]
x=np.arange(4); w=0.36
for ax in (a,b):
    ax.set_facecolor(S); ax.grid(axis="y",color=G,zorder=0); ax.tick_params(length=0,colors=I2)
    [s.set_visible(False) for s in ax.spines.values()]
a.bar(x-w/2-0.01,full,w,color=F,zorder=2,label="Full (High)"); a.bar(x+w/2+0.01,lite,w,color=L,zorder=2,label="Lite (Low)")
for i in range(4):
    a.text(x[i]-w/2,full[i]+2,f"{full[i]:.0f}",ha="center",color=I,fontsize=9.5,fontweight="bold")
    a.text(x[i]+w/2,lite[i]+2,f"{lite[i]:.0f}",ha="center",color=I,fontsize=9.5,fontweight="bold")
a.set_xticks(x); a.set_xticklabels(m,color=I); a.set_ylim(0,165)
a.set_ylabel("dB below the official output (higher = closer)",color=I2)
a.set_title("Match vs official NAM (TONE3000 / NeuralAmpModelerCore)",loc="left",color=I,fontweight="bold")
a.legend(frameon=False,loc="upper center",ncol=2,labelcolor=I,bbox_to_anchor=(0.5,1.01))
cat=["Full","Lite"]; orig=[715,108]; neon=[451,73]; y=np.arange(2)
b.bar(y-w/2-0.01,orig,w,color=O,zorder=2,label="lolgab v0.1.6 (base)"); b.bar(y+w/2+0.01,neon,w,color=F,zorder=2,label="this mod (NEON)")
for i in range(2):
    b.text(y[i]-w/2,orig[i]+15,f"{orig[i]} µs",ha="center",color=I,fontsize=9.5,fontweight="bold")
    b.text(y[i]+w/2,neon[i]+15,f"{neon[i]} µs",ha="center",color=I,fontsize=9.5,fontweight="bold")
b.axhline(1000,color=I2,lw=1,ls="--",zorder=1); b.text(1.45,985,"block limit 1000 µs",ha="right",va="top",color=I2,fontsize=9)
b.set_xticks(y); b.set_xticklabels(cat,color=I); b.set_ylim(0,1080); b.set_ylabel("time per 48-sample block (lower = more headroom)",color=I2)
b.set_title("Speed on the MX5 (Full 1.58× faster)",loc="left",color=I,fontweight="bold")
b.legend(frameon=False,loc="upper right",labelcolor=I,bbox_to_anchor=(1,0.9))
fig.tight_layout(); fig.savefig(r"C:\Users\Starcz\Documents\arsenal\mx5\github\mx5-nam-a2\docs\nam-a2-full-lite.png",facecolor=S); print("ok")

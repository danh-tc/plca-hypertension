import re
p='paper_master.md'; s=open(p,encoding='utf-8').read()
ri=s.index("### References"); re_end=s.index("\n### ",ri+5)
head, refblock, tail = s[:ri], s[ri:re_end], s[re_end:]
lines=refblock.split("\n"); old={}
for l in lines:
    m=re.match(r"(\d+)\. (.*)",l)
    if m: old[int(m.group(1))]=m.group(2)
cit=re.compile(r"\\\[(\d+(?:\s*[,–]\s*\d+)*)\\\]")
def expand(t):
    out=[]
    for part in t.split(","):
        part=part.strip()
        if "–" in part: a,b=map(int,part.split("–")); out+=list(range(a,b+1))
        else: out.append(int(part))
    return out
order=[]
for m in cit.finditer(head+tail):
    ns=expand(m.group(1))
    if all(n in old for n in ns):
        for n in ns:
            if n not in order: order.append(n)
dropped=[k for k in sorted(old) if k not in order]
mp={o:i+1 for i,o in enumerate(order)}
def compress(nums):
    nums=sorted(set(nums)); res=[]; i=0
    while i<len(nums):
        j=i
        while j+1<len(nums) and nums[j+1]==nums[j]+1: j+=1
        res.append(str(nums[i]) if j==i else (f"{nums[i]},{nums[j]}" if j==i+1 else f"{nums[i]}–{nums[j]}")); i=j+1
    return ",".join(res)
def sub(m):
    ns=expand(m.group(1))
    if not all(n in old for n in ns): return m.group(0)
    return "\\["+compress([mp[n] for n in ns])+"\\]"
head=cit.sub(sub,head); tail=cit.sub(sub,tail)
note=[l for l in lines if l.startswith("*")][0]
note=re.sub(r"\d+ tài liệu", f"{len(order)} tài liệu", note)
s=head+"### References\n\n"+note+"\n\n"+"\n".join(f"{i+1}. {old[o]}" for i,o in enumerate(order))+"\n"+tail
open(p,'w',encoding='utf-8').write(s)
print("refs:",len(order),"dropped old:",[ (k,old[k][:30]) for k in dropped])

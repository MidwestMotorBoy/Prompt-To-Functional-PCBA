const {encode}=require('gpt-tokenizer/encoding/o200k_base');const fs=require('fs');
const n=+process.argv[2];
for(const f of fs.readdirSync('out')){const t=fs.readFileSync('out/'+f,'utf8');const k=encode(t).length;
console.log(f.padEnd(34),String(t.length).padStart(9),String(k).padStart(8),(k/n).toFixed(1).padStart(8),String(Math.round(k/n*430)).padStart(9));}

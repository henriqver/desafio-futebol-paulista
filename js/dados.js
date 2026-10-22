/* Desafio Futebol Paulista — leitura dos dados (usado por index.html e conferencia.html) */
function norm(s){return (s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9 ]/g,' ').replace(/\s+/g,' ').trim()}
const slug = s => norm(s).replace(/ /g,'-');
/* =========================================================
   CONFIGURAÇÃO — arquivos lidos do próprio site
   ========================================================= */
const CONFIG = {
  jogadores: 'dados/jogadores.csv',   // Jogador, Times Paulistas que Passou, Todos os Times da Carreira
  quiz:      'dados/quiz.csv',        // Pergunta, Resposta certa, Errada 1, Errada 2, Errada 3
  ranking:   'dados/ranking.csv',     // Jogo, Nome, Pontos, Link do vídeo
  escudos:   'dados/escudos.csv',     // (opcional) Clube, Arquivo — para usar nomes de arquivo diferentes do padrão
  pastaEscudos: 'escudos/',           // padrão: escudos/<nome-do-clube>.png   (ex.: escudos/sao-paulo.png)
  pastaFotos:   'jogadores/',         // padrão: jogadores/<nome-do-jogador>.png (ex.: jogadores/ademir-da-guia.png)
  narracao:     'narracao/'           // áudios gerados por ferramentas/gerar_narracao.py (entram no vídeo)
};
/* como a voz do navegador deve pronunciar alguns nomes (a narração gravada usa a mesma lista) */
const PRONUNCIA = {'Botafogo-SP':'Botafogo de Ribeirão Preto','Juventus-SP':'Juventus da Mooca','Nacional-SP':'Nacional','Comercial-SP':'Comercial',
  'River Plate (URU)':'River Plate','Universidad Católica (EQU)':'Universidad Católica','PSV':'P S V','CSKA Moscou':'CSKA de Moscou',
  'Barcelona-SP':'Barcelona','Flamengo-SP':'Flamengo de Guarulhos','América-SP':'América de Rio Preto','Rio Branco-SP':'Rio Branco de Americana','Independente-SP':'Independente de Limeira','ECUS':'E C U S','USAC':'U S A C'};
const pronuncia = t => PRONUNCIA[t]||t;
/* grafias diferentes do mesmo clube na coluna de times paulistas */
const ALIAS_CLUBE = {'S. Caetano':'São Caetano', 'Sao Paulo':'São Paulo', 'Bragantino':'Red Bull Bragantino'};
const ARTIGO_NA = ['Ponte Preta','Portuguesa','Ferroviária','Inter de Limeira','Francana','Matonense','Internacional de Limeira'];

/* =========================================================
   LEITURA DOS CSV
   ========================================================= */
function lerCSV(texto){
  texto=texto.replace(/^\uFEFF/,'');
  const prim=texto.split(/\r?\n/)[0]||''; const sep=(prim.split(';').length>prim.split(',').length)?';':',';
  const linhas=[]; let campo='', linha=[], aspas=false;
  for(let i=0;i<texto.length;i++){
    const c=texto[i];
    if(aspas){ if(c==='"'){ if(texto[i+1]==='"'){campo+='"'; i++} else aspas=false } else campo+=c }
    else if(c==='"') aspas=true;
    else if(c===sep){ linha.push(campo); campo='' }
    else if(c==='\n'||c==='\r'){ if(c==='\r'&&texto[i+1]==='\n') i++; linha.push(campo); linhas.push(linha); linha=[]; campo='' }
    else campo+=c;
  }
  if(campo!==''||linha.length){ linha.push(campo); linhas.push(linha) }
  const cab=(linhas.shift()||[]).map(h=>h.trim());
  return linhas.filter(l=>l.some(v=>v.trim())).map(l=>Object.fromEntries(cab.map((h,i)=>[h,(l[i]||'').trim()])));
}
const lista = s => (s||'').split(',').map(x=>x.trim()).filter(Boolean);
const clubeOk = c => ALIAS_CLUBE[c]||c;
const col = (r,...nomes) => { for(const n of nomes){ const k=Object.keys(r).find(k=>norm(k)===norm(n)); if(k!==undefined) return r[k] } return '' };
async function baixar(url, obrigatorio){
  try{ const r=await fetch(url,{cache:'no-cache'}); if(!r.ok) throw new Error(r.status); return lerCSV(await r.text()) }
  catch(e){ if(obrigatorio) throw new Error('Não foi possível ler '+url); return [] }
}

/* base carregada */
const DB = {jogadores:[], porClube:new Map(), quiz:[], ranking:{}, mapaEscudos:{}, clubesComEscudo:[], problemas:[]};
let RANKING_FIXO = {};
async function carregarDados(){
  const [jog, quiz, rank, esc] = await Promise.all([baixar(CONFIG.jogadores,true), baixar(CONFIG.quiz), baixar(CONFIG.ranking), baixar(CONFIG.escudos)]);
  const vistos=new Set();
  jog.forEach((r,i)=>{
    const nome=col(r,'Jogador'); if(!nome) return;
    if(vistos.has(norm(nome))){ DB.problemas.push(`Linha ${i+2}: "${nome}" repetido (a segunda linha foi ignorada).`); return }
    vistos.add(norm(nome));
    const paulistas=[...new Set(lista(col(r,'Times Paulistas que Passou')).map(clubeOk))];
    const carreira=lista(col(r,'Todos os Times da Carreira')).map(clubeOk);
    const faltam=carreira.length?paulistas.filter(p=>!carreira.some(c=>norm(c)===norm(p))):[];
    if(faltam.length) DB.problemas.push(`${nome}: ${faltam.join(', ')} está nos times paulistas, mas não na carreira completa (fora do desafio Carreira até ser corrigido).`);
    const j={nome, paulistas, carreira, carreiraOk:carreira.length>=3&&!faltam.length};
    DB.jogadores.push(j);
    paulistas.forEach(c=>{ if(!DB.porClube.has(c)) DB.porClube.set(c,[]); DB.porClube.get(c).push(j) });
  });
  DB.quiz=quiz.map(r=>({q:col(r,'Pergunta'), certa:col(r,'Resposta certa','Certa'), err:[col(r,'Errada 1'),col(r,'Errada 2'),col(r,'Errada 3')]}))
    .filter(q=>q.q&&q.certa&&q.err.every(Boolean)).map(q=>({q:q.q, certa:q.certa, opcoes:[q.certa,...q.err]}));
  const jogos=['carreira','dois-clubes','intruso','escudo','silhueta','quiz'];
  RANKING_FIXO=Object.fromEntries(jogos.map(g=>[g,[]]));
  rank.forEach(r=>{ const g=slug(col(r,'Jogo')), pts=parseInt(String(col(r,'Pontos')).replace(/\D/g,''),10);
    if(RANKING_FIXO[g]&&col(r,'Nome')&&pts>=0) RANKING_FIXO[g].push({nome:col(r,'Nome'), pontos:pts, video:col(r,'Link do vídeo','Video','Link')}) });
  esc.forEach(r=>{ const c=col(r,'Clube'), a=col(r,'Arquivo'); if(c&&a){ DB.mapaEscudos[slug(clubeOk(c))]=a; DB.clubesComEscudo.push(clubeOk(c)) } });
}
/* Imagens: tenta o nome registrado em escudos.csv (aceita alternativas separadas por "|")
   e o nome padrão, com as extensões .png, .PNG, .jpg, .jpeg e .webp */
const EXTS=['.png','.PNG','.jpg','.jpeg','.webp'];
function nomesBase(key){
  const [tipo,id]=key.split(':');
  const reg=tipo==='clube'&&DB.mapaEscudos[id] ? DB.mapaEscudos[id].split('|').map(x=>x.trim()).filter(Boolean) : [];
  return [...reg, id];
}
function candidatos(key){
  const pasta=key.startsWith('clube:')?CONFIG.pastaEscudos:CONFIG.pastaFotos, out=[];
  nomesBase(key).forEach(b=>{ if(/\.(png|jpe?g|webp)$/i.test(b)) out.push(b); else EXTS.forEach(e=>out.push(b+e)) });
  return [...new Set(out)].map(f=>pasta+encodeURIComponent(f.normalize('NFC')));
}
const IMGS=new Map();
function carregarImagem(key){
  if(IMGS.has(key)) return IMGS.get(key);
  const p=(async()=>{
    for(const u of candidatos(key)){
      const im=await new Promise(res=>{ const i=new Image(); const t=setTimeout(()=>res(null),8000);
        i.onload=()=>{clearTimeout(t); res(i)}; i.onerror=()=>{clearTimeout(t); res(null)}; i.src=u });
      if(im) return {im, url:u};
    }
    return null;
  })();
  IMGS.set(key,p); return p;
}
const existe = key => carregarImagem(key).then(r=>!!r);
async function filtrarComImagem(tipo, nomes){ const ok=await Promise.all(nomes.map(n=>existe(tipo+':'+slug(n)))); return nomes.filter((_,i)=>ok[i]) }

// Fixtures and vocab of the ThingSite flow (S1 - S6). Lifted verbatim from the
// legacy single-file page (public/demo/td_screens_live.html) so no value was
// retyped. Every panel that reads from here is badged FIXTURE in the UI.
//
// COUNTER HONESTY - two numbers, never blurred.
//   identities = what DB1 holds (harvested)
//   entities   = registered on a verified licence
//   claimed    = inhabitants. Starts at zero and climbs in public.
// TODO(KJ): identities is rounded. Replace with the measured count.

export const KEYS = [
  ['.gtin','a trade item'], ['.giai','an instrument or asset'],
  ['.gdti','a document, with its version'], ['.cpid','a component inside something'],
  ['.gln','a place'], ['.pgln','a party'], ['.gsrn','an operator or agent'],
  ['.grai','a returnable asset'], ['.sscc','a logistics unit']
];

export const NAV = [
  ['home','Home','หน้าแรก'], ['reveal','Identify','ค้นหา'],
  ['site','ThingSite','เว็บของสิ่งของ'], ['samples','Sample ThingSites','ตัวอย่าง'],
  ['prefix','Get a Prefix','ขอ prefix'], ['whois','WHOIS','ค้นหาเจ้าของ'],
  ['pricing','Pricing','ราคา'], ['login','Log in','ลูกค้าเดิม']
];

export const RECORDS = {
 "acme.example":{
  label:"ACME Corp", id:"urn:epc:id:pgln:9520001000005",
  mint:false, state:"built", demo:true,
  roots:[{prefix:"9520001",gcp_length:7,licence_type:"demonstration",gln:"9520001000005",
    mo:"GS1 (reserved demonstration range)",state:"built",
    doors:[{url:"https://acme.example",country:"—"}],
    provenance:{authority:"GS1 General Specifications 26.0",
      via:"Table 1-4 — GS1 Prefix 952 is the reserved demonstration range",
      read_at:"2026-08-25"}}],
  graph:{nodes:[
    {id:"p",label:"ACME Corp",k:"pgln",g:"b",x:480,y:60},
    {id:"l",label:"Plant 1",k:"gln",g:"b",x:480,y:150},
    {id:"i",label:"an instrument",k:"giai",g:"b",x:270,y:250},
    {id:"c",label:"a part inside it",k:"cpid",g:"b",x:150,y:340},
    {id:"t",label:"a trade item",k:"gtin",g:"b",x:420,y:330},
    {id:"d",label:"its method document",k:"gdti",g:"b",x:700,y:245},
    {id:"a",label:"an operator",k:"gsrn",g:"b",x:760,y:120},
    {id:"s",label:"a pallet",k:"sscc",g:"b",x:830,y:335}],
   edges:[["p","l"],["l","i"],["i","c"],["i","d"],["l","t"],["p","a"],["a","i"],["t","s"]]},
  pillars:{
   P1_identity:{count:6,grades:{b:6},rows:[
     {label:"ACME Corp — the party",key_type:"pgln",urn:"urn:epc:id:pgln:9520001000005",grade:"b",
      source:{url:"GenSpecs 26.0 Table 1-4 — prefix 952 reserved for demonstration"}},
     {label:"Plant 1 — the place",key_type:"gln",urn:"urn:epc:id:sgln:9520001.00001.0",grade:"b",
      source:{url:"derived for the walkthrough"}},
     {label:"An instrument — an individual unit",key_type:"giai",urn:"urn:epc:id:giai:9520001.100001",grade:"b",
      source:{url:"derived for the walkthrough"}},
     {label:"A part inside it",key_type:"cpid",urn:"urn:epc:id:cpi:9520001.200001",grade:"b",
      source:{url:"derived for the walkthrough"}},
     {label:"A trade item — a class, not a unit",key_type:"gtin",urn:null,grade:"b",
      source:{url:"derived for the walkthrough"}},
     {label:"An operator — a service relation",key_type:"gsrn",urn:"urn:epc:id:gsrn:9520001.0000001",grade:"b",
      source:{url:"derived for the walkthrough"}}]},
   P2_drivers:{count:1,grades:{b:1},rows:[
     {label:"A driver descriptor, bound document-to-instrument",key_type:"gdti",urn:"urn:epc:id:gdti:9520001.300001.1",grade:"b",
      source:{url:"derived for the walkthrough"}}]},
   P3_protocols:{count:1,grades:{b:1},rows:[
     {label:"A method document, with its version",key_type:"gdti",urn:"urn:epc:id:gdti:9520001.300002.1",grade:"b",
      source:{url:"derived for the walkthrough"}}]},
   P4_cloud:{count:0,grades:{},rows:[],slot:"in a real estate this is your console"},
   P5_graph:{count:8,grades:{b:8},rows:[
     {label:"8 edges across 8 nodes — one of each key class",key_type:null,urn:null,grade:"b",
      source:{url:"derived for the walkthrough"}}]}}},

 "diazyme.com":{
  label:"Diazyme Laboratories", id:"urn:epc:id:pgln:0817089020009",
  mint:false, state:"verified", owned_by:"General Atomics",
  roots:[{prefix:"0817089",gcp_length:7,licence_type:"company-prefix",gln:"0817089020009",
    mo:"GS1 US",state:"verified",doors:[{url:"https://diazyme.com",country:"US"}],
    provenance:{authority:"GS1 US",via:"Verified by GS1 — Find company (hand-read)",read_at:"2026-08-13"}}],
  graph:{nodes:[
    {id:"pgln",label:"Diazyme Laboratories",k:"pgln",g:"v",x:480,y:60},
    {id:"gln",label:"Poway, CA",k:"gln",g:"v",x:480,y:150},
    {id:"i1",label:"DZ-Lite 3000 Plus",k:"giai",g:"c",x:250,y:245},
    {id:"i2",label:"DZ-Lite c270",k:"giai",g:"c",x:400,y:300},
    {id:"m1",label:"Ferritin method",k:"gdti",g:"v",x:660,y:230},
    {id:"m2",label:"Homocysteine method",k:"gdti",g:"c",x:790,y:300},
    {id:"r1",label:"DZ141A-K reagent",k:"gtin",g:"v",x:150,y:330},
    {id:"r2",label:"DZ122A-CAL calibrator",k:"gtin",g:"v",x:300,y:355},
    {id:"a1",label:"operator",k:"gsrn",g:"slot",x:640,y:120}],
   edges:[["pgln","gln"],["gln","i1"],["gln","i2"],["i1","m1"],["i1","m2"],
          ["i1","r1"],["i1","r2"],["pgln","a1"],["a1","i1"],["m1","r2"]]},
  pillars:{
   P1_identity:{count:184,grades:{v:184},rows:[
     {label:"Device identifier 00817089023529",key_type:"gtin",urn:null,grade:"v",source:{url:"FDA device register"}},
     {label:"Device identifier 00817089023512",key_type:"gtin",urn:null,grade:"v",source:{url:"FDA device register"}},
     {label:"Establishment location",key_type:"gln",urn:"urn:epc:id:sgln:0817089.02000.9",grade:"v",source:{url:"GS1 US — hand-read"}},
     {label:"Are these devices units or models?",key_type:null,urn:null,grade:"slot",source:null,slot:"your answer"}]},
   P2_drivers:{count:6,grades:{b:6},rows:[
     {label:"DZ-Lite 3000 Plus — SiLA feature description",key_type:"gdti",urn:null,grade:"b",source:{url:"DZLite_3000Plus.sila.xml"}},
     {label:"DZ-Lite c270 — SiLA feature description",key_type:"gdti",urn:null,grade:"b",source:{url:"DZLite_c270.sila.xml"}},
     {label:"Middleware driver published by a third party",key_type:null,urn:null,grade:"c",source:{url:"Data Innovations registry"}}]},
   P3_protocols:{count:6,grades:{v:1,c:5},rows:[
     {label:"Ferritin — grounded to the Allotrope grammar",key_type:"gdti",urn:null,grade:"v",source:{url:"AFO 2.1.2"}},
     {label:"Homocysteine · Lp(a) · HbA1c · Fibrinogen · Procalcitonin",key_type:"gdti",urn:null,grade:"c",source:{url:"AFO 2.1.2"}}]},
   P4_cloud:{count:1,grades:{c:1},rows:[
     {label:"AWS IoT Thing — DZ-Lite-3000Plus--0817089-SN0001",key_type:null,urn:null,grade:"c",source:{url:"AWS console — ARN page"}}],slot:"your console"},
   P5_graph:{count:487,grades:{c:487},rows:[
     {label:"487 edges across 251 nodes",key_type:null,urn:null,grade:"c",source:{url:"platform graph"}}]}},
  regulatory:{clearances:32,codes:27,first:2004,latest:2026},
  book:true },

 "beckmancoulter.com":{
  label:"Beckman Coulter", id:null, mint:false, state:"verified",
  roots:[
   {prefix:"5099590",gcp_length:7,licence_type:"company-prefix",state:"verified",
    registered_to:"Beckman Coulter, Inc.",doors:[{url:"https://beckmancoulter.com",country:"US"}],
    provenance:{authority:"GS1 US",via:"Verified by GS1 (hand-read)",read_at:"2026-08-13"}},
   {prefix:"083746100",gcp_length:9,licence_type:null,state:"candidate",
    registered_to:"Beckman Coulter Ireland AND Iris International — two companies on one licence",
    doors:[],provenance:{authority:"GS1 US",via:"device register",read_at:"2026-08-13"}},
   {prefix:"008254708",gcp_length:9,licence_type:"company-prefix",state:"verified",
    registered_to:"Beckman Coulter, Inc. — a second licence, not a duplicate",
    doors:[{url:"https://beckmancoulter.com",country:"US"}],
    provenance:{authority:"GS1 US",via:"Verified by GS1 (hand-read)",read_at:"2026-08-13"}}],
  graph:{nodes:[
    {id:"p1",label:"Beckman Coulter, Inc.",k:"pgln",g:"v",x:270,y:80},
    {id:"p2",label:"two companies, one licence",k:"pgln",g:"c",x:640,y:80},
    {id:"r1",label:"5099590",k:"gln",g:"v",x:180,y:200},
    {id:"r3",label:"008254708",k:"gln",g:"v",x:390,y:200},
    {id:"r2",label:"083746100",k:"gln",g:"c",x:640,y:200},
    {id:"au",label:"AU series",k:"giai",g:"c",x:270,y:315},
    {id:"iq",label:"iQ / Iris",k:"giai",g:"c",x:700,y:315}],
   edges:[["p1","r1"],["p1","r3"],["p2","r2"],["r1","au"],["r3","au"],["r2","iq"]]},
  pillars:{
   P1_identity:{count:0,grades:{},rows:[],slot:"claim a licence and this fills"},
   P2_drivers:{count:1,grades:{c:1},rows:[
     {label:"AU series — parts and documents derivable",key_type:null,urn:null,grade:"c",
      source:{url:"maker class DERIVABLE — 113 parts, 112 documents, 110 confirmed"}}]},
   P3_protocols:{count:0,grades:{},rows:[],slot:"harvest pending"},
   P4_cloud:{count:0,grades:{},rows:[],slot:"your console"},
   P5_graph:{count:0,grades:{},rows:[],slot:"edges appear as pillars are confirmed"}}},

 "shimadzu.com":{
  label:"Shimadzu", id:null, mint:false, state:"verified",
  roots:[{prefix:"454021706",gcp_length:9,licence_type:"company-prefix",state:"verified",
    doors:[{url:"https://shimadzu.com",country:"JP"}],
    provenance:{authority:"GS1 Japan",via:"device register",read_at:"2026-09-03"}}],
  graph:{nodes:[
    {id:"p",label:"Shimadzu",k:"pgln",g:"v",x:480,y:65},
    {id:"nx",label:"Nexera X3",k:"giai",g:"c",x:270,y:180},
    {id:"cbm",label:"CBM-40 controller",k:"cpid",g:"e",x:640,y:170},
    {id:"cto",label:"CTO-40C oven",k:"cpid",g:"slot",x:800,y:265},
    {id:"col",label:"Shim-pack column",k:"gtin",g:"c",x:170,y:300},
    {id:"doc",label:"228-97203A",k:"gdti",g:"v",x:520,y:290},
    {id:"lc",label:"LC-UV method",k:"gdti",g:"c",x:340,y:340}],
   edges:[["p","nx"],["p","cbm"],["cbm","cto"],["nx","col"],["cbm","doc"],["nx","lc"],["doc","cto"]]},
  pillars:{
   P1_identity:{count:845,grades:{c:845},rows:[
     {label:"53 devices on the register",key_type:"gtin",urn:null,grade:"v",source:{url:"device register"}},
     {label:"Nexera X3 Liquid Chromatograph",key_type:"giai",urn:null,grade:"c",source:{url:"shimadzu.com/an — product tree"}},
     {label:"CTO-40C Column Oven",key_type:null,urn:null,grade:"slot",source:null,
      slot:"a column oven is not a column — the maker has not said which"},
     {label:"CBM-40 System Controller",key_type:null,urn:null,grade:"e",source:{url:"228-97203A"},
      reason:"two classes match and neither wins: system | controller"}]},
   P2_drivers:{count:7,grades:{v:7},rows:[
     {label:"The CTO-40C CL is controlled by the CBM-40 CL system controller",key_type:null,urn:null,grade:"v",
      source:{url:"228-97203A.pdf",page_printed:50,page_pdf:58,sha256:"41d33ef0140864b4"}},
     {label:"No command set published for this unit — recorded as a claim, not an absence",key_type:null,urn:null,grade:"v",
      source:{url:"228-97203A.pdf",page_printed:50,page_pdf:58,sha256:"41d33ef0140864b4"}},
     {label:"Cross-vendor: Agilent OpenLab (RC.NET), Thermo Chromeleon 7.2",key_type:null,urn:null,grade:"c",
      source:{url:"/software-informatics/drivers/"}}]},
   P3_protocols:{count:21,grades:{c:19,v:2},rows:[
     {label:"LC-UV — 21 conditions read, 2 validated",key_type:"gdti",urn:null,grade:"c",source:{url:"application notes"}}]},
   P4_cloud:{count:0,grades:{},rows:[],slot:"your console"},
   P5_graph:{count:484,grades:{c:484},rows:[
     {label:"484 edges · 189 nodes · Nexera degree 157",key_type:null,urn:null,grade:"c",source:{url:"platform graph"}}]}}},

 "ga.com":{
  label:"General Atomics", id:null, mint:false, state:"exception", roots:[],
  exception_reason:"no-gs1-licence-on-record",
  provenance:{authority:"GS1 US",via:"Verified by GS1 — Find company (hand-read)",read_at:"2026-08-13"},
  related_rooted:{label:"Diazyme Laboratories",prefix:"0817089",relation:"subsidiary",domain:"diazyme.com"}}
};

export const SHAPE = {
  gtin:'square', giai:'square', cpid:'square', sscc:'square', grai:'square',
  gdti:'triangle',
  pgln:'circle', gln:'circle', sgln:'circle', gsrn:'circle',
  assoc:'diamond'
};

export const KC={ pgln:"#7fd4ff", gln:"#59b4e6", sgln:"#59b4e6", gsrn:"#c9a6ff",
           giai:"#3fd08a", gtin:"#f2c14e", cpid:"#ff9d6e", sscc:"#e0e6ea",
           grai:"#9ad6c0", gdti:"#ff8fa3", assoc:"#19b3b5" };

export const OPACITY={ v:1, b:.92, c:.55, e:.5, slot:.28 };

export const GRADE_LABEL={v:"verified",c:"candidate",e:"exception",b:"built",slot:"slot"};

export const FREE_MAIL=new Set(["gmail.com","yahoo.com","hotmail.com","outlook.com","icloud.com","qq.com","163.com"]);

export const SOURCES = [
  { name:'FDA device register', devices:5129241, prefixes:15243 },
  { name:'NMPA China',          devices:6015000, prefixes:12544 }
];

export const PILLARS=[['P1_identity','Identity'],['P2_drivers','Drivers'],['P3_protocols','Protocols'],
               ['P4_cloud','Cloud & edge'],['P5_graph','The graph']];

export const BOOKS = {
  'diazyme.com': { pages:100, paras:534, segments:['Clinical chemistry — Poway, CA'] },
  'acme.example':{ pages:null, paras:null, segments:['The walkthrough — one segment, built'] }
};

export const FRONT = [
  {k:'cover',    n:'',      t:'Cover and the root'},
  {k:'doctrine', n:'F0–F11',t:'The doctrine — one identity, seven layers'},
  {k:'map',      n:'',      t:'The enterprise map'}
];

export const BACK = [
  {k:'register', n:'',      t:'The consolidated register'},
  {k:'close',    n:'',      t:'The three stacks, and an honest close'},
  {k:'walk',     n:'T7',    t:'The screen-by-screen walk'}
];


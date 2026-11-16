const make = (id, name, collection, type, facts, extra={}) => ({id,name,collection,type,size:Math.round(facts.map(f=>f[2]).join('').length/1024*10)/10,updated:'Sample dataset',...extra,pages:facts.map(([topic,value,text],i)=>({page:i+1,topic,value,text}))});
export const documents = [
make('atlas','Atlas Cloud · Enterprise proposal','Vendor proposals','PDF',[
['Atlas annual subscription','$24,000','Atlas Cloud offers an annual subscription of $24,000 for 100 seats. The quote covers the core workspace and standard integrations.'],
['Atlas implementation fee','$4,500','A mandatory, one-time implementation fee of $4,500 covers migration, configuration and administrator training. This charge is excluded from the annual subscription.'],
['Atlas premium support','$3,600','Premium support costs $3,600 per year and is required for the four-hour response SLA. Standard email support is included without a response-time commitment.'],
['Atlas storage overage','$0.12 per GB','Atlas includes 1,000 GB of storage. Additional storage is billed at $0.12 per GB per month. Overage is excluded from the base quote.'],
['Atlas contract renewal','7%','Atlas may increase subscription prices by 7% at annual renewal. Cancellation requires written notice at least 60 days before renewal.']],{vendor:{name:'Atlas Cloud',base:24000,setup:4500,support:3600,storage:1000,overage:.12,renewal:.07,color:'#8a75da'}}),
make('bloom','Bloom Systems · Business proposal','Vendor proposals','PDF',[
['Bloom annual subscription','$27,600','Bloom Systems charges $27,600 annually for 100 seats. The subscription includes all standard connectors and audit logs.'],
['Bloom implementation fee','$0','Bloom includes implementation and migration at no extra cost. The one-time implementation fee is $0.'],
['Bloom premium support','$0','Bloom includes 24/7 premium support with a four-hour response SLA in its subscription. The additional annual support charge is $0.'],
['Bloom storage overage','$0.08 per GB','Bloom includes 2,000 GB of storage. Additional usage is charged at $0.08 per GB per month. Data export is included.'],
['Bloom contract renewal','3%','Bloom caps annual subscription increases at 3%. Customers may cancel with 30 days of written notice before renewal.']],{vendor:{name:'Bloom Systems',base:27600,setup:0,support:0,storage:2000,overage:.08,renewal:.03,color:'#59aa91'}}),
make('cobalt','Cobalt Works · Growth proposal','Vendor proposals','PDF',[
['Cobalt annual subscription','$21,600','Cobalt Works charges an annual base subscription of $21,600 for 100 seats. Custom integrations are quoted separately.'],
['Cobalt implementation fee','$6,000','Cobalt requires a one-time implementation fee of $6,000 for migration and provisioning. This fee is not included in the advertised subscription.'],
['Cobalt premium support','$4,800','Cobalt premium support costs $4,800 per year for a four-hour response SLA. Standard support has a two-business-day response target.'],
['Cobalt storage overage','$0.18 per GB','Cobalt includes 500 GB of storage. Additional storage is charged at $0.18 per GB per month. A termination data export costs $750, excluded from ongoing operating cost.'],
['Cobalt contract renewal','10%','Cobalt may raise subscription prices by 10% at renewal. The contract automatically renews unless cancellation is received 90 days in advance.']],{vendor:{name:'Cobalt Works',base:21600,setup:6000,support:4800,storage:500,overage:.18,renewal:.10,color:'#dd9b62'}}),
make('security','Security & data handling policy','Company knowledge','PDF',[
['Security encryption at rest','AES-256','The security policy requires AES-256 encryption at rest for all customer records and backups.'],
['Security encryption in transit','TLS 1.2','The minimum transport encryption version is TLS 1.2. Legacy protocols must be disabled.'],
['Security access review','90 days','Security administrators review employee access every 90 days and revoke inactive grants.'],
['Security incident reporting','1 hour','Suspected security incidents must be reported to the security team within 1 hour of discovery.'],
['Security backup retention','35 days','Encrypted daily backups are retained for 35 days. Restoration drills take place quarterly.']]),
make('onboarding','The new teammate handbook','Company knowledge','PDF',[
['Onboarding buddy program','30 days','Every new teammate receives an onboarding buddy for the first 30 days.'],
['Onboarding equipment budget','$1,500','The onboarding equipment budget is $1,500 per new employee, subject to manager approval.'],
['Onboarding orientation','Monday','New teammate orientation takes place every Monday at 10:00 in the company timezone.'],
['Onboarding probation review','90 days','The probation review is scheduled after 90 days of employment.'],
['Onboarding mandatory training','14 days','Security and privacy training must be completed within 14 days of joining.']]),
make('expenses','Travel & expense guidelines','Company knowledge','PDF',[
['Expenses meal allowance','$65','The daily meal allowance for business travel is $65. Itemized receipts are required.'],
['Expenses hotel limit','$220','The standard hotel reimbursement limit is $220 per night, before applicable taxes.'],
['Expenses submission deadline','30 days','Travel expense claims must be submitted within 30 days of the trip ending.'],
['Expenses approval threshold','$500','Single expense claims over $500 require department head approval.'],
['Expenses reimbursement cycle','14 days','Approved expense claims are reimbursed within 14 days of final approval.']]),
make('roadmap','Product roadmap · Q4 2026','Product & engineering','XLSX',[
['Roadmap search launch','November 20','The internal search beta is scheduled for November 20, 2026. This is a planning date, not a delivery guarantee.'],
['Roadmap mobile pilot','December 5','The mobile pilot is planned for December 5, 2026, with 50 internal participants.'],
['Roadmap accessibility target','WCAG 2.2 AA','The product roadmap sets WCAG 2.2 AA as the accessibility target for new interfaces.'],
['Roadmap engineering capacity','24 engineer-weeks','The Q4 search initiative has an allocated capacity of 24 engineer-weeks.'],
['Roadmap beta cohort','150 users','The search beta cohort is limited to 150 users during the first rollout.']]),
make('api','API integration field guide','Product & engineering','PDF',[
['API rate limit','120 requests per minute','The standard API rate limit is 120 requests per minute per authenticated workspace.'],
['API timeout','30 seconds','API clients should use a request timeout of 30 seconds and retry transient failures with jitter.'],
['API webhook retries','5 attempts','Failed webhook deliveries are retried for up to 5 attempts with exponential backoff.'],
['API maximum payload','10 MB','The maximum JSON API request payload is 10 MB. Large files use the upload endpoint.'],
['API token rotation','60 days','Production service tokens must be rotated every 60 days. Never place tokens in browser code.']]),
make('architecture','Search platform · Architecture notes','Product & engineering','IMAGE',[
['Architecture vector dimensions','384','The proposed search platform uses 384-dimensional embeddings for its baseline vector index.'],
['Architecture chunk overlap','80 tokens','The baseline chunking strategy uses an overlap of 80 tokens between adjacent chunks.'],
['Architecture reranking pool','30 candidates','The reranker receives the top 30 candidates after reciprocal rank fusion.'],
['Architecture retrieval count','5 passages','The answer context includes up to 5 passages after relevance and permission filtering.'],
['Architecture ingestion queue','4 workers','The initial ingestion deployment allocates 4 workers for document processing.']]),
make('operations','Customer operations playbook','Company knowledge','PDF',[
['Operations critical response','15 minutes','Critical customer incidents have a first-response target of 15 minutes during staffed hours.'],
['Operations escalation window','2 hours','Unresolved high-priority incidents escalate to the incident commander after 2 hours.'],
['Operations satisfaction target','92%','The customer satisfaction target is 92% positive responses. This is a target, not a measured result.'],
['Operations handoff time','09:00 UTC','The daily support handoff takes place at 09:00 UTC using the shared incident log.'],
['Operations review cadence','weekly','The operations team reviews recurring incidents weekly and assigns remediation owners.']]),
make('finance','Finance snapshot · Q3 2026','Reports & insights','XLSX',[
['Finance quarterly revenue','$2,400,000','The synthetic Q3 2026 finance snapshot records quarterly revenue of $2,400,000.'],
['Finance operating expenses','$1,680,000','The synthetic Q3 2026 snapshot records total operating expenses of $1,680,000.'],
['Finance gross margin','72%','The synthetic Q3 2026 snapshot reports a gross margin of 72%.'],
['Finance cash runway','18 months','The synthetic Q3 2026 forecast estimates a cash runway of 18 months at current burn.'],
['Finance budget variance','4%','The synthetic Q3 2026 operating expense variance is 4% above budget.']]),
make('research','Customer research · Search habits','Reports & insights','PDF',[
['Research participant count','24 participants','The synthetic search research study included 24 participants from four departments.'],
['Research interview duration','45 minutes','Each customer research interview lasted approximately 45 minutes.'],
['Research source preference','83%','In the synthetic study, 83% of participants preferred answers with direct source references.'],
['Research search frequency','8 searches per day','The synthetic study found a median search frequency of 8 searches per day.'],
['Research primary pain point','fragmented knowledge','The most frequently mentioned pain point was fragmented knowledge across disconnected tools.']])
];
export const collections = ['All knowledge','Vendor proposals','Company knowledge','Product & engineering','Reports & insights'];
export const benchmark = documents.flatMap(d=>d.pages.flatMap(p=>[
`What is the ${p.topic.toLowerCase()}?`,
`Find the documented ${p.topic.toLowerCase()} and cite the source.`,
`According to the documents, tell me about ${p.topic.toLowerCase()}.`
].map((question,i)=>({id:`${d.id}-${p.page}-${i}`,question,answer:p.value,reference:{document:d.id,page:p.page},split:i===2?'paraphrase check':'development'}))));

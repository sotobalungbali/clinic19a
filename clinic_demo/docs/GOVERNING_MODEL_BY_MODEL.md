PROLOG — GOVERNING ARCHITECTURE & DOCUMENT AUTHORITY

IMPORTANT:
Prompt ini BUKAN pengganti, revisi, penyederhanaan, atau redefinisi
dari Master Prompt Demo Dataset yang sudah berlaku pada project ini.

Seluruh Master Prompt, specification, architecture document,
composite source, dataset definition, acceptance requirement,
business scenario, persona, volume, relationship, workflow,
exception scenario, KPI/reporting requirement, dan Guardrail
yang sebelumnya telah ditetapkan untuk project ini TETAP BERLAKU.

Master Prompt lama tetap menjadi AUTHORITATIVE DATASET SPECIFICATION
yang menentukan:

- DATA APA yang harus dibuat;
- model dan business object apa yang harus tersedia;
- record apa yang harus dihasilkan;
- jumlah/volume dataset;
- persona;
- company / OU / branch;
- master data;
- transactional data;
- business scenarios;
- workflow;
- relationships;
- positive scenarios;
- negative/exception scenarios;
- reporting/KPI requirements;
- validation requirements;
- serta target acceptance dataset.

Prompt ini mempunyai authority yang BERBEDA.

Prompt ini menjadi:

GOVERNING MIGRATION & EXECUTION ARCHITECTURE

yang menentukan BAGAIMANA seluruh requirement dari Master Prompt lama
tersebut:

- dipetakan menjadi execution journeys;
- dibuat;
- dieksekusi;
- dilanjutkan;
- direkonsiliasi dengan existing legacy data;
- divalidasi;
- dilacak progress-nya;
- di-reset secara aman;
- dibangun kembali;
- diuji idempotency-nya;
- dan diselesaikan sampai Full-Path Runtime Contract Closure.

Dengan demikian berlaku pemisahan authority berikut:

MASTER PROMPT / DATASET SPECIFICATION
                    │
                    │ defines
                    ▼
              WHAT TO BUILD
                    │
                    ▼
        DATASET REQUIREMENTS
                    │
                    │ executed through
                    ▼
THIS GOVERNING MIGRATION /
EXECUTION ARCHITECTURE
                    │
                    │ defines
                    ▼
              HOW TO BUILD
                    │
                    ▼
MODEL-BY-MODEL /
BOUNDED-JOURNEY
DETERMINISTIC GENERATION

============================================================
DOCUMENT PRECEDENCE RULE
============================================================

Gunakan precedence berikut:

LEVEL 1
Actual Odoo 19 CE runtime/source contract

LEVEL 2
Project architecture/specification documents dan Guardrails
yang berlaku

LEVEL 3
Existing Master Prompt Demo Dataset / individual Master Prompts

LEVEL 4
Prompt ini:
Governing Migration & Execution Architecture

LEVEL 5
Current implementation detail dari demo generator

Prompt ini TIDAK BOLEH mengurangi dataset scope yang diwajibkan oleh
Level 1–3.

Jika existing generator bertentangan dengan governing architecture ini,
implementation generator yang harus diperbaiki.

Jika governing execution architecture ini menemukan bahwa suatu
requirement Master Prompt tidak dapat dijalankan karena actual runtime
contract berbeda, JANGAN diam-diam mengubah atau menghapus requirement.

Laporkan requirement tersebut sebagai explicit compatibility/contract
issue dan selesaikan berdasarkan authoritative source.

============================================================
NO DATASET SCOPE REDUCTION
============================================================

Migration ke Model-by-Model / Bounded-Journey TIDAK BOLEH:

- menghapus Master Prompt lama;
- menghilangkan existing dataset requirement;
- mengurangi jumlah scenario;
- menghilangkan persona;
- menghilangkan exception scenario;
- menghilangkan relational requirement;
- menghilangkan workflow;
- menghilangkan report/KPI requirement;
- menghilangkan validation requirement;
- atau menyatakan requirement lama obsolete hanya karena generator
  baru menggunakan struktur journey.

Semua requirement lama harus dipetakan ke Journey Registry.

Jika satu Master Prompt membutuhkan satu journey:

MP-XX
    → Journey XX

maka gunakan satu journey.

Jika satu Master Prompt membutuhkan beberapa bounded journeys:

MP-XX
    ├── Journey XX-A
    ├── Journey XX-B
    └── Journey XX-C

maka pecah secara eksplisit.

Jika beberapa Master Prompt secara runtime merupakan satu atomic
business aggregate:

MP-XX + MP-YY
        ↓
Bounded Journey ZZ

hal tersebut diperbolehkan HANYA jika seluruh requirement masing-masing
Master Prompt tetap dapat ditelusuri dan divalidasi.

============================================================
REQUIREMENT TRACEABILITY — HARD REQUIREMENT
============================================================

Setiap requirement dari Master Prompt lama harus mempunyai traceability
ke journey baru.

Minimal harus dapat dijawab:

Master Prompt mana?
        ↓
Dataset requirement apa?
        ↓
Journey mana yang membuatnya?
        ↓
Model mana yang terlibat?
        ↓
Business key apa yang digunakan?
        ↓
Dependency apa yang diperlukan?
        ↓
Validation apa yang membuktikan keberhasilannya?
        ↓
Reset ownership siapa?
        ↓
Acceptance evidence apa?
        ↓
PASS / PARTIAL / BLOCKED / FAILED?

Jangan ada requirement Master Prompt yang kehilangan execution owner.

Jangan ada journey yang tidak diketahui berasal dari requirement mana.

============================================================
LEGACY PROGRESS IS PART OF MIGRATION
============================================================

Database project mungkin sudah berisi dataset yang dibuat menggunakan
generator lama.

Migration architecture baru TIDAK BOLEH menganggap project dimulai
dari nol.

Sebelum generation baru dilanjutkan:

1. inventory existing demo data;
2. resolve deterministic identity;
3. validate provenance;
4. validate company/OU;
5. validate relationships;
6. validate semantic/business state;
7. classify existing records sebagai:

   ADOPT
   RECONCILE
   REBUILD
   BLOCK
   MISSING

8. reconstruct progress berdasarkan actual database reality.

Dengan demikian progress yang valid dari implementation lama harus
muncul pada Control Center baru.

Contoh:

Master Prompt 01    → Journey 01    PASS       ADOPTED
Master Prompt 02    → Journey 02    PASS       ADOPTED
Master Prompt 03    → Journey 03    PASS       ADOPTED
Master Prompt 04    → Journey 04    PARTIAL
Master Prompt 05    → Journey 05    READY
Master Prompt 06    → Journey 06    WAITING

Jangan mengubah semuanya menjadi 0% hanya karena execution architecture
diganti.

Namun jangan pula menganggap legacy progress sebagai PASS tanpa
revalidation.

============================================================
ONE DATASET — ONE EXECUTION ENGINE
============================================================

Setelah migration:

Master Prompt lama
        ↓
Journey Registry
        ↓
Shared Deterministic Execution Engine
        ↓
Dataset

Execute Current, Execute Next, Resume, Reconcile Existing Dataset,
dan Generate Full HARUS bekerja terhadap dataset specification yang
sama dan menggunakan shared journey execution engine yang sama.

JANGAN membuat "dataset versi lama" dan "dataset versi baru".

Yang berubah adalah EXECUTION ARCHITECTURE.

Yang TIDAK berubah adalah authoritative DATASET INTENT.

============================================================
MIGRATION TARGET
============================================================

Dengan demikian tugas pada prompt berikut BUKAN:

"buat ulang dataset dengan specification baru."

Tugas yang benar adalah:

"MIGRASIKAN cara existing authoritative demo dataset dibangun dan
dikelola dari generator lama menuju Model-by-Model / Bounded-Journey
Deterministic Generation, TANPA kehilangan scope, requirement,
progress valid, relationship, business scenario, dan acceptance
contract yang sudah ditetapkan."

MASTER PROMPT menentukan:

WHAT MUST EXIST.

GOVERNING MIGRATION / EXECUTION ARCHITECTURE menentukan:

HOW IT IS SAFELY AND DETERMINISTICALLY MADE TO EXIST.

Actual runtime validation menentukan:

WHETHER IT REALLY EXISTS AND IS CORRECT.

============================================================
CONTINUE WITH GOVERNING MIGRATION PROMPT
============================================================

Setelah seluruh prinsip authority, precedence, traceability,
legacy reconciliation, dan no-scope-reduction di atas dipahami,
lanjutkan dengan seluruh requirement pada:

MASTER MIGRATION PROMPT
MODEL-BY-MODEL / BOUNDED-JOURNEY
DETERMINISTIC DEMO GENERATION
WITH LEGACY DATASET RECONCILIATION

di bawah ini.

Seluruh bagian prompt berikut harus dibaca sebagai GOVERNING EXECUTION
ARCHITECTURE terhadap Master Prompt project yang SUDAH ADA,
bukan sebagai penggantinya.

MASTER MIGRATION PROMPT
MODEL-BY-MODEL / BOUNDED-JOURNEY DETERMINISTIC DEMO GENERATION
WITH LEGACY DATASET RECONCILIATION
ODOO 19 CE

============================================================
1. OBJECTIVE
============================================================

Lanjutkan pekerjaan pada addon demo yang sedang berjalan dengan
MENGGANTI metode generation lama menjadi:

MODEL-BY-MODEL / BOUNDED-JOURNEY DETERMINISTIC GENERATION

Perubahan ini harus dilakukan terhadap source addon terbaru yang saya
lampirkan/berikan pada project ini.

Tujuan perubahan BUKAN sekadar memecah Generate Full menjadi banyak
tombol.

Tujuan utamanya adalah membuat Demo Dataset Control Center yang:

1. deterministic;
2. observable;
3. auditable;
4. resumable;
5. idempotent;
6. dependency-aware;
7. relation-aware;
8. ownership-aware;
9. reset-safe;
10. compatible dengan data demo yang sudah pernah dibuat oleh
    generator lama;
11. tetap mempunyai Generate Full sebagai end-to-end acceptance path;
12. menggunakan SATU execution engine yang sama untuk eksekusi
    step-by-step maupun Generate Full.

JANGAN memperbaiki error satu per satu secara reaktif.

Sebelum melakukan perubahan, audit seluruh composite source dan seluruh
runtime contract sebagai satu kesatuan.

============================================================
2. IMPORTANT MIGRATION PRINCIPLE
============================================================

JANGAN menghapus seluruh data lama hanya karena generation engine
berubah.

Database mungkin sudah mempunyai sebagian atau banyak demo records
yang dihasilkan metode lama.

Engine baru harus mampu:

LEGACY DATA
    ↓
INVENTORY
    ↓
IDENTITY / PROVENANCE RESOLUTION
    ↓
RELATIONAL VALIDATION
    ↓
ADOPT / RECONCILE / REBUILD / BLOCK
    ↓
RECONSTRUCT PROGRESS
    ↓
CONTINUE GENERATION

Data existing yang valid harus dapat dipertahankan dan diadopsi.

Data existing tidak boleh otomatis dianggap PASS hanya karena record
tersebut ada.

============================================================
3. DO NOT ASSUME ONE MODEL = ONE STEP
============================================================

Gunakan dua jenis execution unit:

A. MODEL STEP
Untuk master/reference model yang dapat berdiri sendiri.

Contoh:

Company
Branch / OU
Location
Product
Vehicle
Driver
Asset
Employee
Treatment Catalog
dan model master lainnya.

B. BOUNDED BUSINESS JOURNEY
Untuk kumpulan model yang merupakan satu business aggregate atau
transactional workflow.

Contoh:

Purchase Order
    purchase.order
    purchase.order.line
    vendor
    product
    company
    downstream workflow dependencies

atau:

Work Order
    work order
    operation/task
    material
    assignment
    related workflow

Parent/child yang secara business transaction merupakan satu aggregate
JANGAN dipisahkan secara artificial hanya demi "satu model satu tombol".

============================================================
4. BUILD A JOURNEY REGISTRY
============================================================

Buat explicit ordered registry seluruh Model Step dan Bounded Journey.

Setiap journey minimal mempunyai metadata:

- sequence/order
- journey_key
- journey_name
- owner addon
- primary model
- dependent models
- prerequisite journeys
- expected deterministic records
- business-key resolver
- company/OU scope
- generation callable
- validation callable
- reconciliation callable
- reset ownership
- workflow policy
- idempotency policy

Contoh conceptual:

01 organization.foundation
02 company.ou
03 locations
04 products.uom
05 vehicle.master
06 driver.master
07 component.master
08 tire.journey
09 fluid.journey
10 fuel.journey
11 transfer.journey
...

Urutan AKTUAL harus ditentukan dari dependency graph source project,
BUKAN dari contoh di atas.

============================================================
5. SINGLE SHARED EXECUTION ENGINE
============================================================

Ini adalah HARD REQUIREMENT.

JANGAN membuat generator terpisah untuk:

- Execute Current
- Execute Next
- Generate Full

Ketiganya harus menggunakan journey registry dan execution method yang
SAMA.

Conceptual:

execute_journey(journey_key)

Execute Current
    → execute_journey(current_journey)

Execute Next
    → resolve next eligible journey
    → execute_journey(next_journey)

Generate Full
    → iterate ordered journey registry
    → execute_journey(each journey)

Dengan demikian:

STEP-BY-STEP execution

dan

GENERATE FULL

harus menjalankan source path, resolver, validation dan business
contract yang sama.

Tidak boleh terdapat dua sources of truth.

============================================================
6. JOURNEY STATE MACHINE
============================================================

Setiap journey harus mempunyai state yang jelas.

Minimal:

WAITING
READY
RUNNING
PASS
PARTIAL
BLOCKED
FAILED

Semantik:

WAITING
Prerequisite belum PASS.

READY
Seluruh prerequisite terpenuhi dan journey dapat dieksekusi.

RUNNING
Sedang dieksekusi.

PASS
Expected dataset + relational + semantic contract telah tervalidasi.

PARTIAL
Sebagian expected data ditemukan/valid tetapi journey belum memenuhi
seluruh contract.

BLOCKED
Tidak aman melanjutkan karena ambiguity, incompatible dependency,
ownership problem, company/OU mismatch, atau unresolved contract.

FAILED
Execution dilakukan tetapi terjadi runtime/business failure.

JANGAN menggunakan PASS hanya karena generator pernah dipanggil.

PASS harus merupakan hasil VALIDATION.

============================================================
7. LEGACY DATASET RECONCILIATION
============================================================

Tambahkan proses:

RECONCILE EXISTING DATASET

atau nama enterprise-equivalent yang sesuai UI addon.

Ketika addon baru pertama kali digunakan setelah migration, engine harus
mampu memeriksa data yang sebelumnya dibuat generator lama.

Untuk setiap expected deterministic record:

1. tentukan canonical business identity;
2. cari existing candidate;
3. periksa provenance;
4. periksa company/OU;
5. periksa relational integrity;
6. periksa required semantic fields;
7. periksa workflow state jika transactional;
8. tentukan classification.

Classification minimal:

ADOPT
RECONCILE
REBUILD
BLOCK
MISSING

============================================================
8. ADOPT CONTRACT
============================================================

ADOPT hanya jika existing record dapat diidentifikasi secara aman dan
memenuhi contract.

Contoh:

Expected Vehicle:
DEMO-VEH-001

Existing:
DEMO-VEH-001

Jika:

business identity valid
company valid
OU valid
relations valid
semantic contract valid

maka:

Created  = 0
Adopted  = 1
Status   = PASS

JANGAN membuat duplicate.

============================================================
9. RECONCILE CONTRACT
============================================================

RECONCILE digunakan jika record dapat diidentifikasi secara pasti,
dimiliki demo dataset, dan aman diperbaiki.

Contoh:

record ditemukan
identity benar
demo ownership terbukti
tetapi field deterministic/provenance tertentu belum lengkap.

Engine dapat melakukan bounded reconciliation jika perubahan tersebut
aman secara business.

JANGAN menggunakan reconcile untuk memaksa transactional records
melewati workflow Odoo.

============================================================
10. REBUILD CONTRACT
============================================================

REBUILD hanya boleh digunakan jika:

- ownership terhadap demo dataset terbukti;
- record aman di-reset/recreate;
- downstream dependency diketahui;
- tidak merusak unrelated production/user data;
- owner API/workflow mengizinkan.

Rebuild harus deterministic dan reversible.

============================================================
11. BLOCK CONTRACT
============================================================

Jika existing legacy data ambigu, JANGAN menebak.

Contoh:

Expected:
DEMO-VEH-017

Found:
2 possible legacy records

Maka:

Journey Status = BLOCKED

Diagnostic harus menjelaskan minimal:

Journey
Model
Expected Business Key
Candidate count
Reason
Required resolution

JANGAN diam-diam memilih record pertama.
JANGAN bergantung pada database ID.
JANGAN membuat duplicate sebagai workaround.

============================================================
12. DETERMINISTIC IDENTITY
============================================================

Generator baru TIDAK BOLEH bergantung pada mutable production
sequence untuk menentukan identity demo record.

JANGAN menggunakan asumsi seperti:

company_id = 3
product_id = 27
vehicle_id = 102

Gunakan deterministic business key / provenance / XMLID / canonical
reference yang stabil sesuai contract masing-masing model.

Production sequence boleh digunakan sebagai display/reference jika
memang diwajibkan owner model, tetapi BUKAN sebagai satu-satunya
identity untuk idempotency/reconciliation.

============================================================
13. RELATIONAL CONTRACT
============================================================

Engine HARUS mendukung dan memvalidasi:

Many2one
One2many
Many2many

Many2one:

Resolve target menggunakan deterministic identity.

One2many:

Validasi melalui ownership/inverse relationship child.

Many2many:

Set expected deterministic relation secara idempotent.

JANGAN menggunakan repeated append yang menghasilkan relational drift.

Untuk setiap journey, validation harus memeriksa bukan hanya jumlah
record tetapi juga hubungan antar-record.

============================================================
14. EXAMPLE RELATIONAL VALIDATION
============================================================

Contoh:

Vehicle DEMO-VEH-001

company_id
    → expected company

driver_ids
    → expected deterministic drivers

component_ids
    → expected deterministic components

Journey tidak boleh PASS jika Vehicle ada tetapi relation salah.

Expected = 25
Found    = 25

BUKAN otomatis PASS.

Harus menjadi misalnya:

Expected             25
Found                25
Identity Valid       25
Company/OU Valid     25
Relations Valid      25
Semantic Valid       25
Duplicates            0

Status              PASS

============================================================
15. TRANSACTIONAL / OWNER API CONTRACT
============================================================

Untuk model transactional seperti:

stock
purchase
accounting
work order
trip
transfer
inventory
billing
payment
atau workflow equivalent,

JANGAN memperbaiki legacy records dengan arbitrary direct write/unlink
jika owner workflow/API mempunyai semantic requirement.

Audit:

- create API
- confirm/post/validate workflow
- cancellation
- reversal
- reset
- unlink constraints
- downstream documents
- accounting/stock effects

Gunakan owner API/workflow yang benar.

============================================================
16. COMPANY / OU / BRANCH / SECURITY CONTRACT
============================================================

Setiap journey harus explicitly mengetahui:

- company
- OU
- branch
- warehouse/location scope
- allowed_company_ids
- user/security context jika relevan

JANGAN bergantung pada accidental current company.

JANGAN menggunakan sudo secara luas untuk menutupi contract problem.

Jika elevated access benar-benar diperlukan untuk bounded demo
operation, scope harus minimal dan alasan harus jelas di source.

============================================================
17. PROGRESS RECONSTRUCTION
============================================================

Setelah Legacy Dataset Reconciliation, reconstruct progress berdasarkan
DATABASE REALITY.

Contoh:

01 Organization       PASS       ADOPTED
02 Company/OU         PASS       ADOPTED
03 Location           PASS       ADOPTED
04 Vehicle            PASS       ADOPTED
05 Driver             PASS       ADOPTED
06 Tire               PASS       ADOPTED
07 Fluid              PARTIAL
08 Fuel               READY
09 Transfer           WAITING

Progress lama TIDAK BOLEH hilang hanya karena engine diganti.

Tetapi progress lama juga TIDAK BOLEH dipercaya hanya berdasarkan state
generator lama.

Reconstruct berdasarkan validation aktual.

============================================================
18. CONTROL CENTER UI
============================================================

Buat Enterprise Demo Dataset Control Center yang membuat progress mudah
saya pahami.

Minimal tampilkan:

Journey Sequence
Journey Name
Primary Model / Scope
Status
Expected
Existing
Adopted
Created
Updated/Reconciled
Invalid
Missing
Duplicate
Last Execution
Last Validation
Error/Diagnostic

Sediakan navigasi/smart button ke detail journey execution jika sesuai
arsitektur addon.

============================================================
19. PRIMARY ACTIONS
============================================================

Control Center minimal harus mempunyai logical actions:

Validate Source Contract
Reconcile Existing Dataset
Execute Current
Execute Next
Generate Full
Validate Dataset
Reset Preview
Execute Safe Reset / Reset Dataset
Rebuild

Nama tombol dapat disesuaikan dengan UI enterprise project, tetapi
semantic contract tidak boleh berubah.

============================================================
20. EXECUTE CURRENT
============================================================

Execute Current hanya menjalankan current READY/PARTIAL journey yang
dipilih.

Sebelum execution:

validate prerequisites
validate compatibility
validate company/OU
validate identity contract
validate ownership
validate required source contracts

Setelah execution:

validate journey
update metrics
update state
determine next READY journey

============================================================
21. EXECUTE NEXT
============================================================

Execute Next harus:

1. mencari journey pertama yang belum PASS;
2. memastikan seluruh prerequisite PASS;
3. execute menggunakan shared execution engine;
4. validate;
5. menyimpan evidence;
6. membuka next journey jika PASS.

Jika FAILED/BLOCKED:

STOP.

Jangan otomatis melewati kegagalan.

============================================================
22. GENERATE FULL
============================================================

Generate Full BUKAN generator alternatif.

Generate Full hanya orchestration atas registry yang sama:

for journey in ordered_registry:
    if journey requires execution:
        execute_journey(journey)
    validate_journey(journey)
    if not PASS:
        STOP

Setelah semua PASS:

FINAL DATASET VALIDATION

============================================================
23. RESUMABILITY
============================================================

Jika generation berhenti pada Journey 18:

01–17 PASS
18 FAILED
19–35 WAITING

setelah source diperbaiki, user harus dapat:

Execute Current / Execute Next

dan melanjutkan dari Journey 18.

JANGAN memaksa regenerate Journey 01–17 jika tidak diperlukan.

Namun prerequisite PASS tetap harus dapat divalidasi ulang.

============================================================
24. IDEMPOTENCY
============================================================

Setiap journey harus mempunyai idempotency contract.

Jika journey PASS dan Execute dijalankan kembali:

Expected existing records harus di-resolve.

Jangan membuat duplicate.

Acceptance target:

Created      = 0
Duplicates   = 0
Relations    = PASS
Semantics    = PASS

Jika reconciliation memang diperlukan:

Created      = 0
Reconciled   = bounded expected count
Duplicates   = 0

============================================================
25. RESET OWNERSHIP
============================================================

Reset harus ownership-aware.

JANGAN menggunakan broad deletion seperti:

name ilike DEMO

atau heuristic longgar lainnya.

Setiap deletable/reversible record harus dapat dibuktikan merupakan
record milik dataset/scenario tersebut.

Reset harus mengetahui dependency order.

Conceptual:

transaction children
    ↓
transactions
    ↓
dependent masters
    ↓
foundation data

sesuai actual dependency graph.

============================================================
26. RESET PREVIEW
============================================================

Reset Preview harus memberikan evidence SEBELUM mutation.

Minimal:

Journey
Model
Record Count
Ownership
Reset Strategy
Blockers
Downstream Dependencies

Jika terdapat unsafe record:

Reset harus BLOCKED.

============================================================
27. SAFE RESET + REBUILD
============================================================

Acceptance path harus mendukung:

Reset Preview
    ↓
Execute Safe Reset
    ↓
Validate Clean Demo-Owned State
    ↓
Rebuild / Generate Full
    ↓
Validate Dataset

Setelah rebuild:

dataset harus menghasilkan business identities dan semantic dataset
yang sama.

Database IDs tidak harus sama.

============================================================
28. ERROR EVIDENCE
============================================================

Jika journey gagal, simpan diagnostic minimal:

journey_key
journey_name
model
business_key
operation
company
OU/branch jika relevan
dependency
exception class
exception message
timestamp

User harus dapat mengetahui:

"gagal di journey mana?"

tanpa membaca seluruh server traceback terlebih dahulu.

Traceback tetap boleh tersedia untuk developer diagnostics.

============================================================
29. NO REACTIVE PATCHING
============================================================

Ini HARD RULE.

Jika ditemukan error pada suatu journey:

JANGAN langsung hanya patch baris yang menyebabkan exception.

Audit full-path contract journey tersebut:

source
dependencies
model schema
field availability
comodel
required fields
ACL
record rules
company/OU
owner API
workflow
sequence
identity
provenance
idempotency
reset
downstream relation
exception paths

Kemudian periksa impact terhadap journey sesudahnya.

Tujuan adalah CONTRACT CLOSURE, bukan error suppression.

============================================================
30. SOURCE COMPATIBILITY
============================================================

Sebelum generation:

audit actual installed source contract.

Periksa minimal:

model existence
field existence
field type
comodel
selection values
required fields
constraints
API method existence
workflow method
ACL
record rules
company scope
dependencies

Jangan mengasumsikan source berdasarkan versi lama.

============================================================
31. LEGACY ENGINE RETIREMENT
============================================================

Setelah migration selesai:

JANGAN mempertahankan legacy generator sebagai engine aktif kedua.

Legacy implementation dapat dipertahankan sementara hanya jika
diperlukan sebagai migration compatibility layer.

Setelah reconciliation selesai:

NEW JOURNEY ENGINE = SINGLE SOURCE OF TRUTH.

============================================================
32. MIGRATION MUST NOT DESTROY VALID PROGRESS
============================================================

Contoh existing database:

Company       COMPLETE
Location      COMPLETE
Vehicle       COMPLETE
Driver        COMPLETE
Tire          COMPLETE
Fluid         PARTIAL
Fuel          NOT CREATED

Expected migration result:

Company       ADOPT → VALIDATE → PASS
Location      ADOPT → VALIDATE → PASS
Vehicle       ADOPT → VALIDATE → PASS
Driver        ADOPT → VALIDATE → PASS
Tire          ADOPT → VALIDATE → PASS
Fluid         RECONCILE → VALIDATE → PASS
Fuel          CREATE → VALIDATE → PASS

JANGAN otomatis reset semuanya ke zero.

============================================================
33. JOURNEY DETAIL
============================================================

Setiap journey idealnya menyediakan detail seperti:

Journey:
08 — Fluid

Expected       : 25
Existing       : 18
Adopted        : 18
Created        : 0
Reconciled     : 0
Missing        : 7
Invalid        : 0
Duplicates     : 0

Dependencies:
Vehicle        PASS
Product/UoM    PASS
Location       PASS

Relations:
vehicle_id     PASS
product_id     PASS
company_id     PASS

Status:
PARTIAL

Action:
EXECUTE CURRENT

Setelah execution:

Expected       : 25
Existing       : 25
Adopted        : 18
Created        : 7
Missing        : 0
Duplicates     : 0

Status:
PASS

============================================================
34. ACCEPTANCE TEST A — LEGACY MIGRATION
============================================================

Dengan database existing dari generator lama:

Upgrade addon.

Run:
Reconcile Existing Dataset

Expected:

- existing valid records tidak duplicate;
- valid records di-adopt;
- partial records teridentifikasi;
- ambiguous records BLOCKED;
- progress reconstructed;
- next valid journey menjadi READY.

============================================================
35. ACCEPTANCE TEST B — STEP-BY-STEP
============================================================

Mulai dari clean/resettable demo state.

Execute:

Journey 01
Validate → PASS

Journey 02
Validate → PASS

...

sampai journey terakhir.

Expected:

ALL JOURNEYS PASS.

============================================================
36. ACCEPTANCE TEST C — FULL GENERATION
============================================================

Safe Reset.

Kemudian:

Generate Full

Expected:

Journey 01 → PASS
Journey 02 → PASS
...
Journey NN → PASS

Final Dataset Validation:

PASS.

============================================================
37. ACCEPTANCE TEST D — IDEMPOTENCY
============================================================

Tanpa reset:

Generate Full lagi.

Expected:

Created      = 0
Duplicates   = 0
Missing      = 0
Relations    = PASS
Dataset      = PASS

Tidak boleh terjadi silent duplicate.

============================================================
38. ACCEPTANCE TEST E — RESET / REBUILD
============================================================

Run:

Reset Preview
Execute Safe Reset
Validate Clean State
Generate Full
Validate Dataset

Expected:

PASS.

Dataset semantic identity setelah rebuild harus sama dengan baseline.

============================================================
39. ACCEPTANCE TEST F — FAILURE / RESUME
============================================================

Simulasikan atau gunakan bounded failure yang aman.

Jika Journey N gagal:

1..N-1 = PASS
N      = FAILED/BLOCKED
N+1..  = WAITING

Setelah root contract diperbaiki:

Execute Current / Execute Next

Expected:

N      = PASS
N+1    = READY

Tidak perlu mengulang seluruh dataset.

============================================================
40. DO NOT BREAK CURRENT ENTERPRISE FEATURES
============================================================

Pertahankan seluruh fitur valid yang sudah ada.

Jangan menghapus:

menus
actions
views
security
reports
wizards
existing valid demo scenarios
business functionality

kecuali memang obsolete dan replacement-nya merupakan bagian explicit
migration.

Migration ini adalah perubahan DEMO GENERATION ARCHITECTURE,
bukan alasan untuk merombak fitur business addon yang tidak terkait.

============================================================
41. FULL-PATH RUNTIME CONTRACT CLOSURE
============================================================

Sebelum menyerahkan hasil, audit seluruh journey registry sebagai satu
graph:

FOUNDATION
    ↓
MASTER DATA
    ↓
RELATIONAL DATA
    ↓
TRANSACTIONS
    ↓
WORKFLOWS
    ↓
REPORTING / KPI
    ↓
FINAL VALIDATION
    ↓
RESET
    ↓
REBUILD
    ↓
IDEMPOTENCY

Periksa setiap dependency edge.

Jangan berhenti hanya karena current reported error sudah hilang.

============================================================
42. ODOO 19 CE REQUIREMENT
============================================================

Semua implementasi harus compatible dengan actual Odoo 19 CE source
yang digunakan project.

Jangan membawa API/field/view syntax dari versi Odoo lama tanpa
memastikan compatibility.

Pertahankan enterprise-grade UX walaupun platform adalah Community
Edition.

============================================================
43. DELIVERABLE
============================================================

Saya tidak membutuhkan respons yang dipenuhi analisis internal,
hipotesis, atau retry reasoning.

Lakukan audit tersebut secara internal.

Deliverable utama yang saya tunggu adalah:

FULL CORRECTED DEMO ADDON

yang sudah mengimplementasikan:

- Model-by-Model / Bounded-Journey generation
- shared execution engine
- journey registry
- deterministic identity
- dependency graph
- legacy reconciliation
- progress reconstruction
- relational validation
- company/OU contract
- transactional owner workflow
- idempotency
- ownership-aware reset
- Reset Preview
- Safe Reset
- Rebuild
- Generate Full
- final validation
- runtime evidence

Jika deliverable project biasanya berupa ZIP:

SERAHKAN FULL CORRECTED ZIP.

Jangan hanya memberikan patch/snippet/diff jika saya meminta full
corrected addon.

============================================================
44. EXECUTION INSTRUCTION
============================================================

Gunakan seluruh source terbaru yang saya lampirkan sebagai authoritative
runtime evidence.

Jangan memperbaiki hanya error terakhir.

Pertama lakukan composite/full-path audit terhadap seluruh addon demo
dan dependency source yang tersedia.

Kemudian migrasikan generation architecture secara menyeluruh ke:

MODEL-BY-MODEL / BOUNDED-JOURNEY
DETERMINISTIC GENERATION

dengan:

LEGACY DATASET RECONCILIATION
+
PROGRESS RECONSTRUCTION
+
SINGLE SHARED EXECUTION ENGINE.

Pertahankan data lama yang valid.

Jangan membuat duplicate.

Jangan menebak legacy identity yang ambigu.

Jangan bergantung pada mutable production sequence sebagai identity.

Jangan menghapus data yang ownership-nya tidak dapat dibuktikan.

Jangan menyatakan journey PASS tanpa validation.

Setelah implementasi, lakukan static/source acceptance terhadap seluruh
journey dan serahkan FULL CORRECTED ADDON yang siap saya upgrade dan
uji.

TARGET AKHIR:

Saya harus dapat membuka Demo Dataset Control Center dan memahami secara
jelas:

- data apa yang sudah dibuat generator lama;
- journey mana yang sudah PASS;
- journey mana yang PARTIAL;
- journey berikutnya yang READY;
- dependency masing-masing journey;
- record yang di-adopt;
- record yang dibuat;
- record yang direconcile;
- record yang invalid/missing;
- titik kegagalan jika ada;
- progress keseluruhan dataset.

Kemudian saya dapat menjalankan:

EXECUTE CURRENT
→ PASS
→ EXECUTE NEXT
→ PASS
→ ...
→ FINAL VALIDATION

atau:

GENERATE FULL

dengan KEDUA jalur menggunakan execution engine dan runtime contract
yang sama.

FINAL TARGET:

DETERMINISTIC
IDEMPOTENT
RELATIONALLY CORRECT
COMPANY/OU SAFE
RESETTABLE
REBUILDABLE
RESUMABLE
AUDITABLE
LEGACY-AWARE
AND FULL-PATH CONTRACT CLOSED.

======================================================================
ENTERPRISE REPORTING DATA SUFFICIENCY & VOLUME REQUIREMENT
FOR MAXIMUM L1–L8 REPORTING COVERAGE
======================================================================

PURPOSE

This requirement is intentionally limited to DATA QUANTITY, DATA DENSITY,
HISTORICAL DEPTH, and DATA VARIETY required to support enterprise reporting.

It MUST NOT define, replace, modify, or interfere with:

- the governing Master Prompt;
- existing demo-data specifications;
- Model-by-Model Deterministic Generation;
- Bounded-Journey Deterministic Generation;
- generation sequence;
- generator implementation;
- reset architecture;
- reconstruction architecture;
- provenance architecture;
- deterministic key strategy;
- idempotency strategy;
- source compatibility;
- workflow implementation;
- business rules;
- report definitions;
- KPI formulas.

All such concerns remain governed by their respective existing prompts
and source application contracts.

This requirement answers ONLY one question:

HOW MUCH AND HOW DIVERSE MUST THE RESULTING DATA BE
SO THAT ALL ENTERPRISE REPORTING LEVELS ARE MEANINGFULLY POPULATED?


======================================================================
1. REPORTING COVERAGE TARGET
======================================================================

The resulting enterprise data population MUST be sufficiently large,
historically deep, relationally rich, and dimensionally diverse to support:

L1. Operational / Transaction Report
L2. Exception & Control Report
L3. Management / Tactical Report
L4. KPI / Performance Report
L5. Analytical / Decision-Support Report
L6. Executive Dashboard / Enterprise Scorecard
L7. Compliance / Audit / Regulatory Report
L8. Stakeholder / External Report

Data sufficiency MUST be evaluated against ALL EIGHT levels.

A dataset is NOT reporting-complete merely because operational
transactions exist.


======================================================================
2. MAXIMUM MEANINGFUL DATA PRINCIPLE
======================================================================

The objective is NOT:

"Create as many records as technically possible."

The objective is:

"Create the maximum meaningful amount of business data necessary
to make every applicable enterprise report, KPI, analysis,
dashboard, scorecard, exception report, compliance report,
and stakeholder report meaningful."

High record count without meaningful variation does NOT satisfy
this requirement.

For example:

100,000 nearly identical transactions

MAY provide less reporting value than:

25,000 transactions distributed meaningfully across time,
organization, status, category, business entity, performance,
exception, and stakeholder dimensions.

Therefore prioritize:

MEANINGFUL REPORTING DENSITY

over:

RAW RECORD COUNT.


======================================================================
3. HISTORICAL DEPTH
======================================================================

Unless explicitly constrained by the governing Master Prompt or
business semantics, reporting-significant transactional data SHOULD
provide:

MINIMUM:
12 months historical coverage

PREFERRED:
18 months historical coverage

ENTERPRISE TARGET:
24 months historical coverage

The population SHOULD be sufficient for:

- daily reporting;
- weekly reporting;
- monthly reporting;
- quarterly reporting;
- year-to-date reporting;
- previous-period comparison;
- year-over-year comparison;
- rolling-period analysis;
- historical trends.

Data MUST NOT be concentrated only in the current month.


======================================================================
4. DATA VOLUME GUIDELINES
======================================================================

The following are default reporting-volume guidelines.

They are NOT mandatory quotas and MUST NOT override business realism.

REFERENCE / MASTER ENTITIES
Preferred population:
20–200 meaningful records per applicable entity type.

LOW-FREQUENCY BUSINESS ENTITIES
Preferred population:
100–500 records where business semantics support this.

MEDIUM-FREQUENCY TRANSACTIONS
Preferred population:
500–2,000 records per important transactional domain.

HIGH-FREQUENCY TRANSACTIONS
Preferred population:
2,000–10,000 records per applicable high-volume domain.

DETAIL / EVENT / HISTORY RECORDS
Preferred population:
5,000–25,000 records where naturally generated by business activity.

For a complete enterprise application, the combined business population
SHOULD normally target approximately:

15,000–50,000 records
for a standard enterprise demonstration;

50,000–150,000 records
for a rich enterprise reporting demonstration.

More than 150,000 records MAY be appropriate for naturally
high-volume applications.

These ranges MUST NOT be used to create artificial filler records.


======================================================================
5. TEMPORAL DENSITY
======================================================================

Reporting-significant transactions MUST be sufficiently distributed
across the historical period.

The data SHOULD include meaningful populations for:

- each active day where applicable;
- each week;
- each month;
- each quarter;
- each reporting year.

The historical population SHOULD include realistic variation:

- normal periods;
- high-volume periods;
- low-volume periods;
- improving periods;
- deteriorating periods;
- peaks;
- troughs;
- seasonal patterns where applicable.

Perfectly flat historical data is NOT sufficient for analytical
demonstration.


======================================================================
6. ORGANIZATIONAL & DIMENSIONAL DENSITY
======================================================================

Where supported by the application, data MUST be distributed across
multiple meaningful reporting dimensions.

Examples include:

- company;
- operating unit;
- branch;
- department;
- warehouse;
- location;
- cost center;
- project;
- product;
- service;
- category;
- asset;
- vehicle;
- equipment;
- employee;
- customer;
- patient;
- student;
- supplier;
- route;
- responsible person;
- business type.

Important comparison dimensions SHOULD normally contain at least
3–5 populated values.

Where the business naturally supports higher cardinality,
prefer 5–20 or more meaningful populated values.

No major enterprise report SHOULD depend almost entirely on a
single dimensional value when the source application supports
multiple values.


======================================================================
7. STATUS DIVERSITY
======================================================================

Where supported by source workflows, reporting data SHOULD include
meaningful populations across applicable statuses such as:

- draft;
- submitted;
- pending;
- approved;
- rejected;
- scheduled;
- in progress;
- partially completed;
- completed;
- cancelled;
- overdue;
- expired;
- failed;
- closed.

Do NOT populate only successful/completed transactions.

Important workflow statuses MUST have enough observations to support:

- counts;
- percentages;
- comparisons;
- trends;
- drill-down.


======================================================================
8. NORMAL, WARNING & EXCEPTION POPULATION
======================================================================

Exception & Control reporting MUST contain meaningful populations.

Where business semantics allow, a useful enterprise demonstration
distribution is approximately:

70–85% Normal / Expected / Compliant

10–20% Warning / Near Threshold / Attention Required

3–10% Exception / Failed / Overdue / Breached / Non-Compliant

These percentages are guidelines only.

They MUST NOT override valid business rules.

The important requirement is that the data contains sufficient
populations of BOTH:

NORMAL BUSINESS BEHAVIOR

and

ABNORMAL / EXCEPTION BUSINESS BEHAVIOR.

A demonstration in which everything is perfect is NOT sufficient
for enterprise reporting.


======================================================================
9. MANAGEMENT REPORTING SUFFICIENCY
======================================================================

Management reports MUST have sufficient data to aggregate by:

- reporting period;
- organizational unit;
- business category;
- responsible party;
- major business object;
- status;
- other application-specific management dimensions.

There MUST be enough underlying transactions so that management
aggregations are meaningful rather than merely displaying a few
sample records.


======================================================================
10. KPI DATA SUFFICIENCY
======================================================================

Every applicable KPI MUST have sufficient underlying observations
to produce meaningful:

- Actual;
- Target;
- Variance;
- Achievement %;
- Previous Period;
- Trend;
- Breakdown;
- Drill-down.

Where applicable, the overall population SHOULD produce examples of:

- above target;
- on target;
- near target;
- below target.

Do NOT make every KPI artificially positive.

A KPI calculated from only token/sample records does NOT satisfy
enterprise reporting requirements.


======================================================================
11. ANALYTICAL DATA SUFFICIENCY
======================================================================

Data volume and variation MUST be sufficient for meaningful:

- trend analysis;
- variance analysis;
- period comparison;
- organizational comparison;
- Pareto analysis;
- aging analysis;
- ranking;
- segmentation;
- distribution analysis;
- cross-tab analysis;
- concentration analysis;
- root-cause exploration;
- drill-down analysis.

Analytical reports MUST have enough observations to expose
patterns rather than merely list transactions.


======================================================================
12. EXECUTIVE DATA SUFFICIENCY
======================================================================

Executive Dashboard and Enterprise Scorecard metrics MUST aggregate
from substantial lower-level business populations.

Executive-level indicators SHOULD support:

Enterprise
→ Company / Business Unit
→ Branch / Department
→ Business Domain
→ KPI / Exception
→ Transaction / Evidence

The top-level dashboard MUST NOT consist of metrics derived from
only a handful of demonstration records.


======================================================================
13. COMPLIANCE & AUDIT DATA SUFFICIENCY
======================================================================

Where applicable, reporting data SHOULD contain meaningful
populations of:

- compliant cases;
- non-compliant cases;
- near-expiry cases;
- expired cases;
- approved actions;
- rejected actions;
- overdue actions;
- corrected exceptions;
- unresolved exceptions;
- historical state changes;
- approval evidence;
- audit evidence.

Compliance demonstration MUST NOT show only 100% compliant cases.

There MUST be enough evidence to demonstrate both:

COMPLIANCE

and

CONTROL FAILURE / EXCEPTION.


======================================================================
14. STAKEHOLDER DATA SUFFICIENCY
======================================================================

Where applicable, sufficient data MUST exist for relevant
stakeholder populations such as:

- board;
- owners;
- management;
- customers;
- suppliers;
- employees;
- patients;
- students;
- partners;
- regulators;
- other application-specific stakeholders.

A stakeholder report containing only one or two token records
does NOT satisfy this requirement.


======================================================================
15. RELATIONAL DENSITY
======================================================================

Data quantity MUST include relational depth.

Where applicable, sufficient populations MUST exist across:

Parent
→ Child
→ Detail
→ Activity
→ Approval
→ Transaction
→ Exception
→ Resolution
→ History

Many2one relationships SHOULD distribute transactions across
multiple parent entities.

One2many relationships SHOULD contain realistic multiple children
where business semantics support them.

Many2many relationships SHOULD contain meaningful multi-entity
relationships.

Reporting must therefore be able to move from:

SUMMARY
→ AGGREGATION
→ DETAIL
→ SOURCE RECORD.


======================================================================
16. NO TOKEN-DATA ACCEPTANCE
======================================================================

The following approach is explicitly insufficient:

"One record exists, therefore the report is populated."

For reporting-significant scenarios, enough observations MUST exist
to demonstrate:

- volume;
- frequency;
- distribution;
- aggregation;
- comparison;
- variance;
- trend;
- exception;
- drill-down.

Token records MAY prove technical functionality.

They DO NOT prove enterprise reporting readiness.


======================================================================
17. REPORTING SUFFICIENCY MATRIX
======================================================================

Before the overall demo population is considered complete,
validate reporting data sufficiency for:

L1 OPERATIONAL / TRANSACTION
Must contain substantial transaction populations.

L2 EXCEPTION & CONTROL
Must contain multiple meaningful exception populations.

L3 MANAGEMENT / TACTICAL
Must support period, organization, and category aggregation.

L4 KPI / PERFORMANCE
Must support statistically meaningful KPI calculation and comparison.

L5 ANALYTICAL / DECISION-SUPPORT
Must contain sufficient historical and dimensional variation.

L6 EXECUTIVE DASHBOARD / SCORECARD
Must aggregate meaningful lower-level populations.

L7 COMPLIANCE / AUDIT / REGULATORY
Must contain both positive evidence and exception evidence.

L8 STAKEHOLDER / EXTERNAL
Must contain sufficient stakeholder-specific populations.

All applicable levels MUST PASS.


======================================================================
18. REPORTING DATA SUFFICIENCY SUMMARY
======================================================================

At final validation, provide a concise population summary containing
at least:

Historical Coverage:
XX months

Master / Reference Records:
XXXX

Transactional Records:
XXXX

Transaction Detail / Lines:
XXXX

Historical / Event Records:
XXXX

Normal / Compliant Records:
XXXX

Warning / Attention Records:
XXXX

Exception / Non-Compliant Records:
XXXX

Major Reporting Dimensions Populated:
XXXX

Total Relevant Business Records:
XXXX


Reporting Coverage:

L1 Operational / Transaction              PASS / FAIL
L2 Exception & Control                    PASS / FAIL
L3 Management / Tactical                  PASS / FAIL
L4 KPI / Performance                      PASS / FAIL
L5 Analytical / Decision-Support          PASS / FAIL
L6 Executive Dashboard / Scorecard        PASS / FAIL
L7 Compliance / Audit / Regulatory        PASS / FAIL
L8 Stakeholder / External                 PASS / FAIL


======================================================================
19. FINAL HARD GATE
======================================================================

Do NOT declare enterprise reporting data sufficient merely because
generation completed successfully.

The final acceptance condition is:

ENTERPRISE REPORTING DATA SUFFICIENCY = PASS

only when all applicable L1–L8 reporting layers have enough
underlying data to produce meaningful enterprise reporting.


======================================================================
20. FINAL PRINCIPLE
======================================================================

This requirement governs QUANTITY AND REPORTING DENSITY ONLY.

It MUST NOT redefine HOW records are generated.

Generation methodology remains entirely governed by the previously
established:

MODEL-BY-MODEL / BOUNDED-JOURNEY DETERMINISTIC GENERATION
ARCHITECTURE.

This requirement begins where that architecture ends:

THE GENERATION ARCHITECTURE DETERMINES
HOW THE DATA IS CREATED.

THIS REQUIREMENT DETERMINES
WHETHER ENOUGH MEANINGFUL DATA EXISTS
TO POWER THE COMPLETE ENTERPRISE REPORTING STACK.

The required reporting stack is:

OPERATIONAL
→ EXCEPTION & CONTROL
→ MANAGEMENT
→ KPI
→ ANALYTICAL
→ EXECUTIVE
→ COMPLIANCE / AUDIT
→ STAKEHOLDER

The governing objective is:

MAXIMUM MEANINGFUL REPORTING COVERAGE,
NOT MAXIMUM MEANINGLESS RECORD COUNT.

END OF ENTERPRISE REPORTING DATA SUFFICIENCY & VOLUME REQUIREMENT
======================================================================





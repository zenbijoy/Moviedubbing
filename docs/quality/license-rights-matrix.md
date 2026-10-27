# License, rights, and production-route matrix

Status: initial Phase 0 control; legal/model governance review required  
Last updated: 2026-08-14

## Binding rule

`UNVERIFIED` means **forbidden in production builds, final exports, customer media processing, and
commercial benchmark promotion**. It does not mean “probably allowed.” Only a reviewed matrix change
to `APPROVED`, tied to exact code/model/weight/provider versions and territories, opens a route.

`BLOCKED` means known information conflicts with the intended commercial route or required evidence
is unavailable. `PROHIBITED` is a product-policy ban. A benchmark score, user opt-in, or developer
configuration cannot override these states.

There is currently no approved ASR, diarization, translation-provider, cloned/reference voice,
source-separation, or lip-sync production route in this matrix.

## Candidate component and service routes

| Route | Intended use | Current disposition | Known concern / missing evidence | Evidence required before approval | Owner |
| --- | --- | --- | --- | --- | --- |
| Signed FFmpeg/FFprobe distribution build | Probe, decode, proxy, mix, mux, encode | UNVERIFIED | Exact build flags, codec/patent exposure, LGPL/GPL choice, notices and source-offer obligations not frozen | Binary/source manifest, build configuration, license inventory, patent review by target market, redistribution plan | Media + Legal |
| PySide6/Qt runtime | Windows desktop UI | UNVERIFIED | Commercial/LGPL route and deployment/linking obligations not approved for the product package | Exact versions, selected license route, notices/source/relinking compliance plan, installer review | Desktop + Legal |
| faster-whisper/CTranslate2-class route | Local ASR/alignment | UNVERIFIED | Candidate name is not an approved engine package; code, model weights, training-data claims and dependencies vary | Exact package/lock/SBOM, code licenses, model card, weight license/hash, commercial-use and privacy review, language evidence | Speech + Model Governance |
| pyannote-class route | Diarization/embeddings | UNVERIFIED | Package/model access terms, weight license, biometric implications and dataset provenance not approved | Exact packages/weights/hashes, terms, biometric DPIA, consent scope, retention policy, per-language DER evidence | Speech + Privacy/Legal |
| Demucs-class route | Source separation fallback | UNVERIFIED | Maintenance, distribution, weight/training-data rights and commercial suitability unresolved | Maintained fork/package decision, complete transitive license/weight evidence, quality limitations and fallback disclosure | Audio + Legal |
| F5-TTS-class pretrained route | Local voice/TTS | BLOCKED | Enterprise plan flags candidate pretrained weights as non-commercial; no commercially approved replacement weight route is recorded | Separately licensed commercial weights or independently approved training route, complete provenance, consent and territory scope | Voice + Legal |
| Chatterbox-class route | Local multilingual voice | UNVERIFIED | Exact implementation/weights and their commercial/training-data terms not selected | Exact code/model/weight manifests, commercial rights, safety evaluation, voice consent workflow, `bn-BD`/`hi-IN` evidence | Voice + Model Governance |
| Fish-Speech-class route | Local multilingual voice | UNVERIFIED | Exact implementation/weights and their commercial/training-data terms not selected | Same evidence as every voice route; no approval by family name | Voice + Model Governance |
| Stock synthetic voice library | Licensed non-cloned voice | UNVERIFIED | Supplier, voices, languages, territories, derivative/export terms and revocation process not selected | Executed supplier agreement, voice IDs, territory/language/use matrix, expiry/revocation/export terms | Product + Legal |
| Reference-conditioned/cloned performer voice | Character voice | UNVERIFIED | No performer-specific consent/license grant can be assumed from source-media rights | Per-subject evidence, permitted purpose/languages/territories, expiry/revocation/approver, biometric/privacy review | Production + Legal/Privacy |
| OpenAI official API route | Translation/reasoning/QC | UNVERIFIED | Exact service/model, commercial terms, retention/training controls, DPA, regions, data classes and cost policy not approved | Executed account terms/DPA, official endpoint, model/version policy, residency/retention configuration, disclosure and audit controls | Providers + Legal/Privacy |
| Google Gemini official API route | Translation/reasoning/QC | UNVERIFIED | Same provider/data-governance evidence is unresolved | Exact authorized product endpoint and the full provider approval packet | Providers + Legal/Privacy |
| DeepSeek official/authorized API route | Translation/reasoning/QC | UNVERIFIED | Exact authorized endpoint, terms, data location/retention/training, sanctions/export and reliability review unresolved | Provider approval packet including target-market and data-transfer review | Providers + Legal/Security |
| Unofficial/reverse-engineered ChatGPT/Gemini/DeepSeek endpoints | Any production operation | PROHIBITED | Authorization, stability, security, privacy and terms cannot be established by adapter code | Not approvable as an unofficial route; replace with an official contracted endpoint | Security + Legal |
| MuseTalk-class route | Fast lip-sync preview | UNVERIFIED | Exact code/weights, training-data rights, likeness/biometric scope, watermark/provenance and commercial terms unresolved | Exact package/weight evidence, consent scope, visual safety/QC, provenance and per-territory review | Vision + Legal/Privacy |
| LatentSync-class route | Final lip-sync candidate | UNVERIFIED | Same visual/likeness and supply-chain evidence unresolved | Exact package/weight evidence plus final-render quality and fallback review | Vision + Legal/Privacy |
| C2PA implementation/tooling | Generated-media provenance | UNVERIFIED | Implementation, container support, signing key custody and interoperability not selected | Exact SDK/tooling license, signing/key design, compatibility results and disclosure policy | Security + Export |
| Inter Font Family | UI Typography (OFL 1.1) | APPROVED | Free open-source redistribution with UI | Bundled in resources/fonts/ | Desktop UI |
| Noto Sans Bengali | Bengali Typography (OFL 1.1) | APPROVED | Free open-source redistribution with UI, full conjunct rendering | Bundled in resources/fonts/ | Desktop UI |
| Lucide Iconography | Crisp 16/20px vector icons (ISC) | APPROVED | Free open-source permissive license with UI | Bundled in resources/icons/ | Desktop UI |

Candidate family names describe evaluation targets only. Approval never transfers from one fork,
package version, model card, checkpoint, quantization, fine-tune, or provider SKU to another.

## Benchmark dataset routes

| Dataset/cohort | Current disposition | Commercial license | Participant/performer consent | Provider disclosure | Production benchmark use |
| --- | --- | --- | --- | --- | --- |
| Internal English (`en`) golden cohort | UNVERIFIED / not populated | No approved evidence recorded | No approved evidence recorded | None approved | FORBIDDEN |
| Internal Bengali (`bn-BD`) golden cohort | UNVERIFIED / not populated | No approved evidence recorded | No approved evidence recorded | None approved | FORBIDDEN |
| Internal Hindi (`hi-IN`) golden cohort | UNVERIFIED / not populated | No approved evidence recorded | No approved evidence recorded | None approved | FORBIDDEN |
| Third-party/public corpora | UNVERIFIED / none selected | Dataset-specific review absent | Dataset-specific review absent | None approved | FORBIDDEN |
| Customer/project media | NOT A DEFAULT BENCHMARK DATASET | Project-specific source rights do not imply research/model evaluation rights | Voice/likeness consent may be separately required | Project policy only | FORBIDDEN unless a separate written benchmark grant is approved |

## Approval record requirements

An `APPROVED` row must name or link to all of the following:

- exact component/provider/model/weight identifiers and SHA-256 manifests;
- code, dependency, model, weight, dataset and media licenses;
- commercial use, redistribution, generated-output and derivative-work analysis;
- languages, purposes, target countries/territories, expiry and revocation behavior;
- privacy/data-protection assessment, voice/biometric/likeness scope, and provider data flow;
- export-control/sanctions and local regulatory review where applicable;
- security/SBOM/vulnerability/signature review;
- required attribution, notices, source offer, watermark and provenance obligations;
- approving engineering owner, legal/privacy owner, security/model-governance owner, and dates;
- benchmark evidence IDs and accepted quality/performance limits.

Approval is version-bound and expires when its evidence expires. Revocation or a materially changed
license/model/provider term blocks new generation and new final export until re-review. Historical
artifacts remain subject to the incident/remediation decision; they are never silently regenerated.

This matrix is an engineering control record, not legal advice or a certification claim.

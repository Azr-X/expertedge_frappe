# ExpertEdge Build Plan

## Business Context
Official India partner for CMA Australia & New Zealand. Leads from ads → qualify → counsel → pre-approval payment → CMA registration → balance → enrollment. Program fee AUD 3,500, 5% lump-sum discount (AUD 3,325), AUD 200 pre-approval.

## Architecture
- `EE Lead` = lightweight intake + qualification (~100:1 ratio)
- `EE Student` = converted candidate (billing, CMA, enrollment)
- Convert to Student button copies data across
- One Sales Invoice per student (AUD), multiple Payment Entries via EE Nomod Payment Link
- Company base currency AED, billing in AUD (multi-currency)
- Hierarchy: EE Program → EE Batch → EE Student

## Build Order (incremental, one at a time, migrate after each)

### Phase 1: Masters
- [x] Save plan.md
- [ ] 1. EE Program (master, named by program_name)
- [ ] 2. EE Batch (master, naming series EE-BATCH-.YYYY.-.###)
- [ ] 3. EE Lead Source (master, named by source_name) + fixture seeds
- [ ] 4. EE Document Type (master, named by document_type) + fixture seeds

### Phase 2: Settings
- [ ] 5. ExpertEdge Settings (Single doctype)

### Phase 3: Child Tables
- [ ] 6. EE Document (istable=1)
- [ ] 7. EE Activity (istable=1)
- [ ] 8. EE Call Log (istable=1)

### Phase 4: Core DocTypes
- [ ] 9. EE Lead (with controller, client script, buttons)
- [ ] 10. EE Counselling Session (with controller)
- [ ] 11. EE Student (with controller, client script, buttons)
- [ ] 12. EE Nomod Payment Link (with controller, stub)

### Phase 5: Roles & Permissions
- [ ] 13. Create roles: EE Telecaller, EE Academic Counsellor, EE Finance, EE Manager
- [ ] 14. Set permissions + permlevel on billing fields

### Phase 6: Automations & Hooks
- [ ] 15. hooks.py (doc_events, scheduler_events)
- [ ] 16. tasks.py (SLA checks)
- [ ] 17. Nomod webhook stub (api/nomod_webhook.py)

### Phase 7: Lead Intake
- [ ] 18. Shared normalizer (intake.py)
- [ ] 19. Web Form (program-enquiry)
- [ ] 20. REST webhook endpoint (api/lead_webhook.py)
- [ ] 21. Sample CSV for bulk import

### Phase 8: Workspace
- [ ] 22. ExpertEdge workspace (shortcuts, number cards, charts, quick lists)

### Phase 9: Reports
- [ ] 23. Conversion Funnel report
- [ ] 24. Telecaller Performance report
- [ ] 25. Call Activity report
- [ ] 26. Counsellor Performance report
- [ ] 27. Payment Collection report

### Phase 10: Email Templates
- [ ] 28. Six email template fixtures

### Phase 11: Workflows (FINAL — only after everything works)
- [ ] 29. EE Lead Workflow
- [ ] 30. EE Student Workflow

## Key Decisions (Locked)
- Frappe/ERPNext v15
- Billing in AUD on AED-base company
- SI created + submitted at billing start
- Roles created fresh
- Conversion at Confirmed stage
- Program → Batch → Student hierarchy
- Workflows deferred to final phase

## Values Needed from User
1. Site name + Company name
2. AED bank/cash account (deposit_account)
3. Service Item + Income Account (or create CMA Program Fee)


test


#!/bin/bash                                                                                                                                                                                                                                                 
echo "=== Deploy started at $(date) ===" >> ~/frappe-bench/logs/deploy.log
cd ~/frappe-bench/apps/expertedge                                                                                                                                                                                                                           
git pull >> ~/frappe-bench/logs/deploy.log 2>&1                                                                                                                                                                                                           
cd ~/frappe-bench                                                                                                                                                                                                                                           
bench --site erp.expertedge.info migrate >> ~/frappe-bench/logs/deploy.log 2>&1
bench --site erp.expertedge.info clear-cache >> ~/frappe-bench/logs/deploy.log 2>&1                                                                                                                                                                         
bench build --app expertedge >> ~/frappe-bench/logs/deploy.log 2>&1
sudo supervisorctl restart all >> ~/frappe-bench/logs/deploy.log 2>&1                                                                                                                                                                                       
echo "=== Deploy finished at $(date) ===" >> ~/frappe-bench/logs/deploy.log
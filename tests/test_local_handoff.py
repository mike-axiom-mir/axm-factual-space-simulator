import copy, json, re, tomllib, unittest
from pathlib import Path
from axm_star_sim.bridge_visual_core import resolve_start_package, pin_start_package_for_save
from axm_star_sim.handoff import audit_package
from axm_star_sim.migration import create_migration_proposal, assess_migration_proposal, create_visual_reconstruction_packet

ROOT=Path(__file__).resolve().parents[1]

class LocalHandoffTests(unittest.TestCase):
    def test_current_version_consistent(self):
        py=tomllib.loads((ROOT/'pyproject.toml').read_text(encoding="utf-8"))['project']['version']
        init=re.search(r'__version__ = "([^"]+)"',(ROOT/'src/axm_star_sim/__init__.py').read_text(encoding="utf-8")).group(1)
        handoff=json.loads((ROOT/'data/local_handoff_manifest.json').read_text(encoding="utf-8"))['version']
        self.assertEqual((py,init,handoff),('0.15.0','0.15.0','0.15.0'))
    def test_handoff_paths_exist(self):
        h=json.loads((ROOT/'data/local_handoff_manifest.json').read_text(encoding="utf-8"))
        paths=[h['canonical_open_file'],h['start_here'],h['human_handoff'],h['machine_handoff']]+h['canonical_registries']+h['demo_entrypoints']+h['required_docs']
        self.assertFalse([p for p in paths if not (ROOT/p).exists()])
    def test_root_commitment_pinned(self):
        h=json.loads((ROOT/'data/local_handoff_manifest.json').read_text(encoding="utf-8")); k=json.loads((ROOT/'data/immutable_root_kernel.json').read_text(encoding="utf-8"))
        self.assertEqual(h['root_commitment_sha256'],k['root_commitment_sha256'])
    def test_missing_demo_regression_is_fixed(self):
        self.assertTrue((ROOT/'output/ship_interior_demo/ship_interior_console.html').exists())
        self.assertTrue((ROOT/'output/rooted_crew_demo/rooted_crew_console.html').exists())
    def test_builder_schema_protects_capability_gap(self):
        s=json.loads((ROOT/'data/builder_capability_declaration_schema.json').read_text(encoding="utf-8"))
        self.assertTrue(s['policy']['capability_gap_is_not_failure_or_disobedience'])
        gap=s['properties']['capability_gaps']['items']['properties']
        self.assertEqual(gap['punishment_or_quality_penalty_allowed']['const'],False)
    def test_builder_example_is_honest_partial(self):
        e=json.loads((ROOT/'output/local_handoff/BUILDER_CAPABILITY_DECLARATION_EXAMPLE.json').read_text(encoding="utf-8"))
        self.assertEqual(e['honest_completion_state'],'partial')
        self.assertTrue(e['capability_gaps'])
    def test_future_backlog_unique_and_unimplemented(self):
        items=json.loads((ROOT/'data/future_potential_backlog.json').read_text(encoding="utf-8"))['items']; ids=[x['id'] for x in items]
        self.assertEqual(len(ids),len(set(ids))); self.assertTrue(all(x['status']=='IDEA_NOT_IMPLEMENTED' for x in items))
    def test_migration_visual_reconstruction_allowed(self):
        pin=pin_start_package_for_save(resolve_start_package())
        p=create_migration_proposal(pin,'visual_reconstruction',{'target_render_profile_id':'axm.render.future.v2'})
        self.assertEqual(assess_migration_proposal(p)['verdict'],'ACCEPT')
    def test_migration_rejects_pinned_ship_change(self):
        pin=pin_start_package_for_save(resolve_start_package())
        p=create_migration_proposal(pin,'format_wrapper',{'ship_blueprint_id':'different.ship'})
        self.assertEqual(assess_migration_proposal(p)['verdict'],'REJECT')
    def test_migration_rejects_root_replacement(self):
        pin=pin_start_package_for_save(resolve_start_package())
        p=create_migration_proposal(pin,'format_wrapper',{'replace_roots':True})
        self.assertEqual(assess_migration_proposal(p)['verdict'],'REJECT')
    def test_explicit_fork_requires_new_id(self):
        pin=pin_start_package_for_save(resolve_start_package())
        p=create_migration_proposal(pin,'explicit_fork',{})
        self.assertEqual(assess_migration_proposal(p)['verdict'],'HOLD')
    def test_visual_packet_does_not_change_semantics(self):
        pin=pin_start_package_for_save(resolve_start_package())
        packet=create_visual_reconstruction_packet(pin,'abc','renderer.v2',2)
        self.assertFalse(packet['semantic_change_allowed']); self.assertEqual(packet['original_start_pin'],pin)
    def test_no_container_paths_in_key_handoff(self):
        for name in ['README.md','START_HERE.txt','LOCAL_INTAKE_HANDOFF.txt','MACHINE_INTAKE.json']:
            self.assertNotIn('/mnt/data/',(ROOT/name).read_text(encoding="utf-8"))
    def test_readme_is_current(self):
        self.assertTrue((ROOT/'README.md').read_text(encoding="utf-8").startswith('# AXM Factual Star Adventure Simulator v0.15.0'))
    def test_quick_audit_without_manifest_is_valid(self):
        result=audit_package(ROOT,full=False,check_manifest=False)
        self.assertTrue(result['valid'],result)
    def test_pyproject_has_handoff_and_migration_cli(self):
        scripts=tomllib.loads((ROOT/'pyproject.toml').read_text(encoding="utf-8"))['project']['scripts']
        self.assertIn('axm-handoff',scripts); self.assertIn('axm-migration',scripts)
    def test_machine_intake_points_to_canonical_files(self):
        m=json.loads((ROOT/'MACHINE_INTAKE.json').read_text(encoding="utf-8"))
        self.assertTrue(all((ROOT/p).exists() for p in m['read_first']))
    def test_output_snapshot_manifest_covers_generated_files(self):
        manifest=json.loads((ROOT/'output/OUTPUT_SNAPSHOT_MANIFEST.json').read_text(encoding="utf-8"))
        expected=set(manifest['files'])
        actual={p.relative_to(ROOT).as_posix() for p in (ROOT/'output').rglob('*') if p.is_file() and p.name not in {'OUTPUT_SNAPSHOT_MANIFEST.json','OUTPUT_CHECKSUMS.sha256'}}
        self.assertEqual(expected,actual)
    def test_package_manifest_separates_generated_output(self):
        manifest=json.loads((ROOT/'PACKAGE_MANIFEST.json').read_text(encoding="utf-8"))
        self.assertFalse(any(path.startswith('output/') for path in manifest['files']))
    def test_migration_policy_forbids_history_rewrite(self):
        policy=json.loads((ROOT/'data/save_migration_policy_registry.json').read_text(encoding="utf-8"))['policies'][0]
        self.assertTrue(any('ledger rewrite' in x for x in policy['forbidden_changes']))

if __name__=='__main__': unittest.main()

"""Portable experimental geometry, driver BOM and fixed-gain export."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import tempfile
import zipfile

from .boundary_lab import _contained, _read_json, sha256
from .export_validation import validate_export
from .optimisation import candidate_record
from .search_results import load_completed_search


def export_search(search: Path, output: Path) -> dict:
    """Export a verified completed search without running CAD or acoustic solves."""
    search, output = Path(search).absolute(), Path(output).absolute()
    if output.exists():
        raise FileExistsError(f'output already exists: {output}')
    controls, result, brief, _, winner, gain = load_completed_search(search)
    trial = search / f"trial-{result['winner_index']:03d}"
    geometry = trial / 'geometry'
    geometry_bytes = (geometry / 'geometry.json').read_bytes()
    if hashlib.sha256(geometry_bytes).hexdigest() != result['winner'].get('geometry_manifest_sha256'):
        raise ValueError('geometry is not bound to the completed search; legacy searches cannot be exported')
    manifest = json.loads(geometry_bytes)
    if (manifest['design'] != candidate_record(winner)['design']
            or not manifest.get('front_chamber_back_walls_verified')):
        raise ValueError('winning geometry is inconsistent or lacks verified chamber walls')
    export_checks = validate_export(geometry)
    design = winner['design']
    rows = []
    for role, driver, quantity in [('throat', winner['drivers'][0], 1),
                                   ('side', winner['drivers'][1], design.driver_count - 1)]:
        price = brief.prices[driver.id]
        rows.append({'role': role, 'driver_id': driver.id, 'revision': driver.revision,
                     'quantity': quantity, 'unit_price': price, 'line_total': price * quantity,
                     'record_sha256': driver.content_hash,
                     'provenance_kind': driver.provenance.kind})
    bom = {'currency': brief.currency, 'scope': 'drivers_only',
           'price_provenance': 'user_supplied_search_brief', 'items': rows,
           'total': winner['cost'], 'physical_qualification': False,
           'excluded_costs': ['amplifier', 'DSP', 'material', 'printing', 'hardware', 'assembly']}
    if brief.build_budget is not None:
        from .build_cost import estimate_build_cost
        estimate=estimate_build_cost(brief.build_budget,manifest,winner['cost'])
        if not estimate['within_budget'] or estimate!=result['winner'].get('build_cost'):
            raise ValueError('winning build cost differs from declared budget and CAD')
        bom.update(scope='drivers_CAD_material_and_declared_allowances',driver_subtotal=winner['cost'],
                   build_cost=estimate,total=estimate['estimated_total_cost'],
                   excluded_costs=['Anything not included in CAD material, driver prices or the declared other allowance'])
    project = _read_json(trial / 'system/project.blab.json')
    ports = project['physical_system']['excitation_ports']
    expected = {'component:throat'} | {
        f'component:{name}' for name, _, _ in design.entry_sites}
    representatives = {'component:throat'} | {
        f'component:{name}' for name, _, _ in design.solver_entry_sites}
    if (project.get('symmetry', 'off') != design.solver_symmetry
            or len(ports) != len(representatives) or {p['component_id'] for p in ports} != representatives):
        raise ValueError('winning source layout differs from generated geometry')
    gains = {'kind': 'relative_voltage_basis_gains', 'hardware_preset': False,
             'absolute_voltage_calibrated': False,
             'description': 'Multipliers of the saved native excitation basis; no filters or delays.',
             'channels': [{'excitation_port_id': p['id'], 'component_id': p['component_id'],
                           'gain': 1.0 if p['component_id'] == 'component:throat' else gain,
                           'phase_deg': 0.0, 'delay_s': 0.0} for p in ports]}
    if brief.acoustic_objectives is not None:
        settings=result['winner']['drive_settings']
        from .acoustic_objectives import freeze_brief
        freeze_brief(brief,gain,settings)
        gains={'kind':'parallel_mid_bank_and_hf_lr4','hardware_preset':False,
               'absolute_voltage_calibrated':False,'drive_settings':settings,
               'parallel_mid_bank':result['winner']['parallel_mid_bank'],
               'description':'Two ideal amplifier channels; analogue LR4 model requires DSP hardware mapping and calibration.',
               'channels':[{'id':'mid_bank','component_ids':sorted(expected-{'component:throat'}),
                            'wiring':'parallel','gain':gain,'polarity':settings['mid_polarity'],
                            'highpass_hz':settings['mid_highpass_hz'],'lowpass_hz':settings['upper_crossover_hz'],'delay_s':0.},
                           {'id':'hf','component_ids':['component:throat'],'gain':1.,'polarity':1,
                            'highpass_hz':settings['upper_crossover_hz'],'delay_s':settings['hf_delay_s']}]}
    if design.solver_symmetry == 'xy':
        gains['simulation_source_groups'] = [
            {'excitation_port_id': port['id'], 'representative_component_id': port['component_id'],
             'physical_component_ids': ([port['component_id']] if port['component_id'] == 'component:throat'
                 else [port['component_id'], port['component_id'].replace('positive', 'negative')]),
             'excitation': 'equal_voltage_on_all_group_members'} for port in ports]
    side_locations = manifest['sources']
    if len(side_locations)!=design.driver_count-1 or {f"component:{s['id']}" for s in side_locations} != expected-{'component:throat'}:
        raise ValueError('geometry source placements are incomplete or inconsistent')
    throat_location = {'id': 'throat', 'front_center_m': [0, 0, 0], 'rear_center_m': None,
                       'motion_axis': [0, 0, 1], 'radius_m': design.throat_radius_m,
                       'rear_load': 'none', 'kind': 'ideal_piston_interface'}
    assembly = {'units': 'mm', 'placement': 'parts already share assembled coordinates',
                'parts': [{'file': 'geometry/' + row['file'],
                           'transform': [[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]}
                          for row in export_checks['parts']],
                'source_locations_m': [throat_location, *side_locations], 'hardware_fit_verified': False}
    bundle = {'schema_version': 1, 'kind': 'experimental_search_build_bundle',
              'status': 'complete', 'print_qualified': False, 'physical_validation': False,
              'finalist_validation_included': False, 'search_winner_index': result['winner_index'],
              'source_sha256': controls, 'runtime': result['runtime'],
              'electrical_validation': result['winner']['electrical_validation'],
              'export_checks': export_checks, 'files_sha256': {},
              'limitations': ['Search export does not establish mesh convergence or physical qualification',
                             'Ideal driver interfaces require mounting, sealing and print planning',
                             'Driver-only cost uses supplied prices; synthetic records are not products']}
    # Stage a complete ZIP, then publish without replacing an existing user file.
    with tempfile.NamedTemporaryFile(dir=output.parent, suffix='.zip', delete=False) as temp:
        staged = Path(temp.name)
    try:
        with zipfile.ZipFile(staged, 'w', zipfile.ZIP_DEFLATED) as archive:
            def member(name):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                return info
            def write(name, data):
                if name in bundle['files_sha256']:
                    raise ValueError('duplicate bundle file')
                archive.writestr(member(name), data)
                bundle['files_sha256'][name] = hashlib.sha256(data).hexdigest()
            def write_json(name, data):
                write(name, (json.dumps(data, indent=2, allow_nan=False) + '\n').encode())
            write('geometry/geometry.json', geometry_bytes)
            for entry in manifest['files']:
                relative = entry['path']
                if PurePosixPath(relative).is_absolute() or '..' in PurePosixPath(relative).parts or '\\' in relative:
                    raise ValueError('unsafe geometry archive path')
                path = _contained(geometry, relative)
                data = path.read_bytes()
                if hashlib.sha256(data).hexdigest() != entry['sha256']:
                    raise ValueError('geometry changed during export')
                write('geometry/' + relative, data)
            write_json('bom.json', bom)
            write_json('gain-settings.json', gains)
            write_json('assembly.json', assembly)
            write_json('candidate.json', candidate_record(winner))
            write('brief.json', (search / 'brief.json').read_bytes())
            write('score.json', (trial / 'score.json').read_bytes())
            write('README.txt', b'Experimental MEH search export\n\n'
                  b'Use material parts in geometry/parts; air and analysis meshes are not print parts.\n'
                  b'STEP/STL coordinates are millimetres. Material parts already share assembly coordinates.\n'
                  b'bom.json lists selected driver quantities and supplied driver-only prices.\n'
                  b'gain-settings.json preserves relative simulation gains, not a hardware crossover preset.\n'
                  b'No supports, mounting hardware, sealing, slicer or physical print qualification is supplied.\n'
                  b'Exporting a search does not run or claim finalist validation. Keep the original raw search evidence.\n'
                  b'bundle.json contains source identities and SHA-256 hashes of the other bundled files.\n')
            if (load_completed_search(search)[0] != controls
                    or (geometry / 'geometry.json').read_bytes() != geometry_bytes):
                raise ValueError('search or geometry changed during export')
            archive.writestr(member('bundle.json'), json.dumps(bundle, indent=2, allow_nan=False) + '\n')
        digest = sha256(staged)
        os.link(staged, output)
        summary={'status': 'complete', 'output': str(output), 'sha256': digest,
                'driver_count': design.driver_count, 'driver_cost': winner['cost'],
                'currency': brief.currency, 'print_qualified': False,
                'finalist_validation_included': False}
        if brief.build_budget is not None:
            summary['estimated_total_cost']=bom['total']
        return summary
    finally:
        staged.unlink(missing_ok=True)

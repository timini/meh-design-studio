"""Manufacturable geometry proposal, not an acoustically validated loudspeaker.

Units are millimetres. Run with the repository CAD extra installed.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import zipfile

import cadquery as cq
from meh_studio.export_validation import validate_export

LENGTH=450.0
THROAT=12.5
MOUTH=300.0
WALL=4.0
ENTRY=80.0
PORT=30.0
FACE=12.0
SPLITS=(130.0,250.0,370.0)


def radial(z):
    return THROAT+(MOUTH-THROAT)*z/LENGTH


def cylinder(radius, depth, origin=(0,0,0), direction=(0,0,1)):
    return cq.Solid.makeCylinder(radius,depth,cq.Vector(*origin),cq.Vector(*direction))


def rounded_plate(width, height, z=0, radius=6):
    return cq.Workplane('XY').rect(width,width).extrude(height).edges('|Z').fillet(radius).val().translate((0,0,z))


def build():
    slope=(MOUTH-THROAT)/LENGTH
    angle=math.atan(slope)
    shell=cq.Solid.makeCone(THROAT+WALL,MOUTH+WALL,LENGTH)
    bore=cq.Solid.makeCone(THROAT,MOUTH,LENGTH)
    shell=shell.fuse(cylinder(48,8,(0,0,-8)))
    bores=[bore,cylinder(THROAT,10,(0,0,-9))]
    # Throat bolt pattern: Celestion CDX1-1445, four M6 on 76 mm PCD.
    for i in range(4):
        a=math.radians(90*i)
        bores.append(cylinder(3.3,10,(38*math.cos(a),38*math.sin(a),-9)))
    shell=shell.fuse(cylinder(MOUTH+12,8,(0,0,LENGTH-8)))
    # External split flanges and longitudinal split ribs keep hardware out of the air path.
    for z in SPLITS:
        shell=shell.fuse(cylinder(radial(z)+14,8,(0,0,z-4)).cut(cylinder(radial(z)-5,10,(0,0,z-5))))
        for i in range(8):
            a=math.radians(22.5+45*i)
            r=radial(z)+9
            bores.append(cylinder(2.25,12,(r*math.cos(a),r*math.sin(a),z-6)))
    profile=[(radial(126)+2,126),(radial(LENGTH)+2,LENGTH),
             (radial(LENGTH)+16,LENGTH),(radial(126)+16,126)]
    rib=cq.Workplane('XZ').polyline(profile).close().extrude(8,both=True).val()
    for i in range(8):
        a=45*i
        shell=shell.fuse(rib.rotate((0,0,0),(0,0,1),a))
        for z in (190,310,410):
            hole=cylinder(2.25,22,(radial(z)+10,-11,z),(0,1,0))
            bores.append(hole.rotate((0,0,0),(0,0,1),a))
    # Four identical wall-normal mountings on one axial ring.
    locations=[]
    local=cylinder(PORT+4,16,(0,0,-12)).fuse(
        cq.Solid.makeCone(PORT+4,41.3,8,cq.Vector(0,0,4)),rounded_plate(108,8,4,radius=28))
    local_air=cylinder(PORT,46,(0,0,-42)).fuse(cq.Solid.makeCone(PORT,37.3,8,cq.Vector(0,0,4)),
                                                   cylinder(37.3,2,(0,0,12)))
    mount_holes=[]
    # Actual 3FE25 mounting pattern: 92 mm PCD, four 4.5 mm clearance holes.
    for i in range(4):
        a=math.radians(45+90*i)
        mount_holes.append(cylinder(2.25,10,(46*math.cos(a),46*math.sin(a),3)))
    for u,v in ((48,0),(-48,0),(0,48),(0,-48)):
        mount_holes.append(cylinder(2.25,10,(u,v,3)))
    for i in range(4):
        a=math.radians(i*90)
        normal=(math.cos(angle)*math.cos(a),math.cos(angle)*math.sin(a),-math.sin(angle))
        origin=(radial(ENTRY)*math.cos(a),radial(ENTRY)*math.sin(a),ENTRY)
        plane=cq.Plane(origin=origin,xDir=(-math.sin(a),math.cos(a),0),normal=normal)
        shell=shell.fuse(local.moved(plane.location))
        bores.extend(shape.moved(plane.location) for shape in [local_air,*mount_holes])
        locations.append({'name':f'mid_{i+1}','angle_deg':90*i,'origin_mm':list(origin),
                          'normal':list(normal),'face_offset_mm':FACE,'plane':plane})
    for shape in bores:
        shell=shell.cut(shape)
    shell=shell.clean()
    # Driver rear cover: clear 88 mm square by 120 mm deep; flange face is z=0.
    cap=rounded_plate(108,6,radius=28).fuse(rounded_plate(96,124,radius=10))
    cavity=rounded_plate(88,122,-2,radius=4)
    cap=cap.cut(cavity)
    for u,v in ((48,0),(-48,0),(0,48),(0,-48)):
        cap=cap.cut(cylinder(2.25,8,(u,v,-1)))
    # Two lead holes; seal around wires after assembly.
    for x in (-6,6):
        cap=cap.cut(cylinder(1.5,8,(x,0,119)))
    cap=cap.clean()
    if not shell.isValid() or len(shell.Solids())!=1:
        raise ValueError('invalid or disconnected horn body')
    if not cap.isValid() or len(cap.Solids())!=1:
        raise ValueError('invalid rear cover')
    return shell,cap,locations


def wedge(low,high):
    points=[(0,0),(1000*math.cos(math.radians(low)),1000*math.sin(math.radians(low))),
                     (1000*math.cos(math.radians(high)),1000*math.sin(math.radians(high)))]
    return cq.Workplane('XY').polyline(points).close().extrude(600).val().translate((0,0,-100))


def generate(output):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    body,cover,locations=build()
    files=[];manufacturing=[];volumes={}
    def save(shape,name,step=False):
        if not shape.isValid() or len(shape.Solids())!=1 or shape.Volume()<=0:
            raise ValueError(f'invalid printable part: {name}')
        path=output/'parts'/f'{name}.stl';path.parent.mkdir(parents=True,exist_ok=True)
        cq.exporters.export(shape,str(path),tolerance=.10,angularTolerance=.08)
        volumes[path.stem]=shape.Volume()/1e9
        bb=shape.BoundingBox()
        files.append({'path':path.relative_to(output).as_posix(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                      'size_bytes':path.stat().st_size})
        if step:
            cq.exporters.export(shape,str(path.with_suffix('.step')))
        return {'file':str(path.relative_to(output)),'bounds_mm':[bb.xlen,bb.ylen,bb.zlen],
                'solid_volume_mm3':shape.Volume()}
    main=save(body,'horn_body',True)
    cap_print=cover.rotate((0,0,0),(1,0,0),180).translate((0,0,124))
    cap_record=save(cap_print,'rear_cover_print_four',True)
    cap_record['to_mount_local']={'rotate_x_deg':180,'translate_mm':[0,0,124]}
    # Low-cost fit coupons precede the full prototype print.
    coupon=rounded_plate(108,4,radius=28).cut(cylinder(37.3,6,(0,0,-1)))
    for i in range(4):
        a=math.radians(45+90*i)
        coupon=coupon.cut(cylinder(2.25,6,(46*math.cos(a),46*math.sin(a),-1)))
    for u,v in ((48,0),(-48,0),(0,48),(0,-48)):
        coupon=coupon.cut(cylinder(2.25,6,(u,v,-1)))
    save(coupon,'fit_checks/mid_mount_coupon')
    hf_coupon=cylinder(48,4).cut(cylinder(THROAT,6,(0,0,-1)))
    for i in range(4):
        a=math.radians(i*90)
        hf_coupon=hf_coupon.cut(cylinder(3.3,6,(38*math.cos(a),38*math.sin(a),-1)))
    save(hf_coupon,'fit_checks/hf_mount_coupon')
    # Core translates up to sit at z=0; each sector is centred and sits flat at z=0.
    core=body.intersect(cq.Solid.makeBox(1000,1000,SPLITS[0]+100,cq.Vector(-500,-500,-100)))
    core=core.translate((0,0,8))
    record=save(core,'print/core')
    record['assembly_transform']={'rotate_z_deg':0,'translate_mm':[0,0,-8]}
    manufacturing.append(record)
    total=core.Volume()
    bands=[(130,250),(250,370),(370,450)]
    for band,(low,high) in enumerate(bands,1):
        slab=cq.Solid.makeBox(1000,1000,high-low,cq.Vector(-500,-500,low))
        ring=body.intersect(slab)
        for i in range(8):
            part=ring.intersect(wedge(45*i,45*(i+1))).clean()
            total+=part.Volume()
            angle=45*i+22.5
            rotated=part.rotate((0,0,0),(0,0,1),-angle)
            bb=rotated.BoundingBox()
            centre=[(bb.xmin+bb.xmax)/2,(bb.ymin+bb.ymax)/2,low]
            printable=rotated.translate(tuple(-v for v in centre))
            record=save(printable,f'print/band_{band}_sector_{i+1}')
            record['assembly_transform']={'translate_before_rotate_mm':centre,'rotate_z_deg':angle}
            manufacturing.append(record)
    if abs(total/body.Volume()-1)>1e-6:
        raise ValueError('segmentation changed material volume')
    if any(max(row['bounds_mm'])>250 for row in manufacturing+[cap_record]):
        raise ValueError('a print part exceeds the declared 250 mm envelope')
    # Check conservative driver/cap envelopes against each other and the HF driver.
    caps=[cover.translate((0,0,FACE)).moved(row['plane'].location) for row in locations]
    hf=cylinder(45,52,(0,0,-60))
    interferences=[]
    for i,cap in enumerate(caps):
        for j,other in enumerate(caps[:i]):
            volume=cap.intersect(other).Volume()
            if volume>1e-5: interferences.append([i,j,volume])
        if cap.intersect(hf).Volume()>1e-5: interferences.append([i,'HF',cap.intersect(hf).Volume()])
    for i,cap in enumerate(caps):
        if cap.intersect(body).Volume()>1e-4: interferences.append([i,'horn_body',cap.intersect(body).Volume()])
    if interferences: raise ValueError(f'cover interference: {interferences}')
    for row in locations: row.pop('plane')
    manifest={'schema_version':1,'status':'complete','units':{'cad_and_stl':'mm'},'files':files,'material_volume_m3':volumes,
              'kind':'mechanical_prototype','acoustic_validation':False,'print_tested':False,
              'target_mid_band_hz':[240,3000],'target_tweeter_band_hz':[3000,20000],
              'mouth_clear_diameter_mm':600,'horn_length_mm':LENGTH,'port_diameter_mm':2*PORT,
              'entry_axial_mm':ENTRY,'normal_wall_mm':WALL/math.sqrt(1+((MOUTH-THROAT)/LENGTH)**2),
              'drivers':{'mid':'4 x FaitalPRO 3FE25-8','hf':'1 x Celestion CDX1-1445-8'},
              'body':main,'rear_cover':cap_record,'mountings':locations,'print_parts':manufacturing,
              'rear_cavity_gross_litres':(88*88*120-(4-math.pi)*4**2*120)/1e6,
              'rear_driver_displacement_litres':.125,
              'total_material_litres':(body.Volume()+4*cover.Volume())/1e6,
              'segmentation_volume_error_fraction':abs(total/body.Volume()-1),
              'cover_interferences':interferences,
              'limitations':['Unmeasured cone profile and front-cavity acoustics',
                 'No full coupled acoustic simulation or crossover tuning for this new four-around-one-ring layout',
                 'No measured 240 Hz–3 kHz flatness, distortion, directivity or efficiency claim',
                 'Nominal catalogue fit; verify one interface coupon with actual hardware before full printing',
                 'No mechanical load or print qualification; support the mouth and throat externally']}
    (output/'geometry.json').write_text(json.dumps(manifest,indent=2))
    validation=validate_export(output)
    (output/'mesh-checks.json').write_text(json.dumps(validation,indent=2))
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=generate(args.output)
    print(json.dumps({k:result[k] for k in ['body','total_material_litres','rear_cavity_gross_litres']},indent=2))

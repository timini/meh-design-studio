"""Import and inspect explicit complex CSV measurements without qualification."""
import argparse
import json
from pathlib import Path
import sys
from .measurements import import_measurement,read_measurement


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    add=commands.add_parser('import')
    add.add_argument('csv',type=Path)
    add.add_argument('--metadata',type=Path,required=True)
    add.add_argument('--calibration',type=Path)
    add.add_argument('--output',type=Path,required=True)
    show=commands.add_parser('inspect');show.add_argument('directory',type=Path)
    args=parser.parse_args(argv)
    try:
        if args.command=='import':
            import_measurement(args.csv,args.metadata,args.output,calibration_path=args.calibration)
        metadata,arrays=read_measurement(args.output if args.command=='import' else args.directory)
        print(json.dumps({'evidence':'imported_not_qualified','metadata':metadata.model_dump(mode='json'),
            'samples':len(arrays['frequency_hz']),'samples_within_declared_band':int(arrays['within_declared_band'].sum())}))
        return 0
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print(json.dumps({'error':str(exc)}),file=sys.stderr)
        return 2


if __name__=='__main__': raise SystemExit(main())

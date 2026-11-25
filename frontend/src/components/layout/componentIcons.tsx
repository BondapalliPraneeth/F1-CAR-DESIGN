import {
  Armchair,
  ArrowDownToLine,
  Box,
  CircleDot,
  Cog,
  Disc3,
  Fan,
  Flame,
  Layers,
  type LucideIcon,
  PanelTop,
  Shield,
  ShieldHalf,
  Spline,
  Thermometer,
  Triangle,
  Waves,
  Wind,
  Wrench,
  Zap,
} from "lucide-react";

const BY_ID: Record<string, LucideIcon> = {
  front_wing: Wind,
  nose_cone: Triangle,
  front_suspension: Spline,
  front_tyres: CircleDot,
  front_brakes: Disc3,
  monocoque: Shield,
  halo: ShieldHalf,
  cockpit: Armchair,
  sidepods: PanelTop,
  radiators: Thermometer,
  floor: Layers,
  venturi_tunnels: Waves,
  diffuser: Fan,
  rear_suspension: Spline,
  rear_tyres: CircleDot,
  rear_brakes: Flame,
  rear_wing: Wind,
  drs: ArrowDownToLine,
  power_unit: Zap,
  rear_crash_structure: Box,
};

const BY_CATEGORY: Record<string, LucideIcon> = {
  aerodynamic: Wind,
  structural: Shield,
  thermal: Thermometer,
  powertrain: Zap,
  mechanical: Cog,
};

export function componentIcon(id: string, category?: string): LucideIcon {
  return BY_ID[id] ?? (category ? BY_CATEGORY[category] : undefined) ?? Wrench;
}

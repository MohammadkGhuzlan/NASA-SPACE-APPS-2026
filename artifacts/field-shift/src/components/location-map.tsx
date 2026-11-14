import { useEffect } from "react";
import "leaflet/dist/leaflet.css";
import { MapContainer, TileLayer, CircleMarker, Polygon, Polyline, useMap, useMapEvents } from "react-leaflet";

type Pt = [number, number];

function ClickHandler({ onClick }: { onClick: (p: Pt) => void }) {
  useMapEvents({ click: (e) => onClick([e.latlng.lat, e.latlng.lng]) });
  return null;
}

function FlyTo({ center }: { center: Pt | null }) {
  const map = useMap();
  useEffect(() => {
    if (center) map.flyTo(center, Math.max(map.getZoom(), 12), { duration: 0.9 });
  }, [center?.[0], center?.[1]]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

export function LocationMap({
  point, vertices, closed, drawing, onMapClick, className,
}: {
  point: Pt | null;
  vertices: Pt[];
  closed: boolean;
  drawing: boolean;
  onMapClick?: (p: Pt) => void;
  className?: string;
}) {
  return (
    <MapContainer center={point ?? [20, 10]} zoom={point ? 12 : 2} worldCopyJump className={className} style={{ cursor: drawing ? "crosshair" : "pointer" }}>
      <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      {onMapClick && <ClickHandler onClick={onMapClick} />}
      <FlyTo center={point} />
      {closed && vertices.length >= 3 && (
        <Polygon positions={vertices} pathOptions={{ color: "hsl(20 58% 46%)", weight: 2.5, fillColor: "hsl(92 24% 60%)", fillOpacity: 0.3 }} />
      )}
      {!closed && vertices.length > 1 && <Polyline positions={vertices} pathOptions={{ color: "hsl(20 58% 46%)", weight: 2.5, dashArray: "6 6" }} />}
      {vertices.map((v, i) => (
        <CircleMarker key={i} center={v} radius={5} pathOptions={{ color: "hsl(44 50% 96%)", weight: 2, fillColor: "hsl(20 58% 46%)", fillOpacity: 1 }} />
      ))}
      {point && (
        <CircleMarker center={point} radius={9} pathOptions={{ color: "hsl(44 50% 96%)", weight: 3, fillColor: "hsl(152 40% 20%)", fillOpacity: 1 }} />
      )}
    </MapContainer>
  );
}

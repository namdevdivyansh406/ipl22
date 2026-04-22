import React from 'react';
import { Activity, Heart, Zap, AlertTriangle, Frown } from 'lucide-react';

const Scoreboard = ({ data }) => {
  // Calculate average of the latest over if data exists
  const latestData = data && data.length > 0 ? data[data.length - 1] : null;

  return (
    <div className="glass-card" style={{ display: 'flex', justifyContent: 'space-around', flexWrap: 'wrap', gap: '1rem', marginBottom: '2rem' }}>
      <ScoreItem icon={<Activity color="#3b82f6" />} label="Tension" score={latestData?.tension || 0} colorClass="tension" />
      <ScoreItem icon={<Heart color="#10b981" />} label="Joy" score={latestData?.joy || 0} colorClass="joy" />
      <ScoreItem icon={<Frown color="#ef4444" />} label="Anger" score={latestData?.anger || 0} colorClass="anger" />
      <ScoreItem icon={<Zap color="#f59e0b" />} label="Surprise" score={latestData?.surprise || 0} colorClass="surprise" />
      <ScoreItem icon={<AlertTriangle color="#8b5cf6" />} label="Disbelief" score={latestData?.disbelief || 0} colorClass="disbelief" />
    </div>
  );
};

const ScoreItem = ({ icon, label, score, colorClass }) => (
  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '0.5rem' }}>
    <div style={{ marginBottom: '0.5rem' }}>{icon}</div>
    <div style={{ color: '#94a3b8', fontSize: '0.875rem', marginBottom: '0.25rem' }}>{label}</div>
    <div className={`score-badge ${colorClass}`} style={{ fontSize: '1.25rem' }}>
      {score.toFixed(1)}
    </div>
  </div>
);

export default Scoreboard;

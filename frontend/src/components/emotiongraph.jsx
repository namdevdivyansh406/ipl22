import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const EmotionGraph = ({ data }) => {
  if (!data || data.length === 0) {
    return <div style={{ textAlign: 'center', padding: '2rem', color: '#94a3b8' }}>Waiting for match data...</div>;
  }

  return (
    <div style={{ width: '100%', height: 400 }}>
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 20, right: 30, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
          <XAxis dataKey="over" stroke="#94a3b8" />
          <YAxis stroke="#94a3b8" domain={[0, 10]} />
          <Tooltip 
            contentStyle={{ backgroundColor: 'rgba(30, 41, 59, 0.9)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }}
            itemStyle={{ fontWeight: 'bold' }}
          />
          <Legend />
          <Line type="monotone" dataKey="tension" stroke="#3b82f6" strokeWidth={3} activeDot={{ r: 8 }} />
          <Line type="monotone" dataKey="joy" stroke="#10b981" strokeWidth={3} />
          <Line type="monotone" dataKey="anger" stroke="#ef4444" strokeWidth={3} />
          <Line type="monotone" dataKey="surprise" stroke="#f59e0b" strokeWidth={3} />
          <Line type="monotone" dataKey="disbelief" stroke="#8b5cf6" strokeWidth={3} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default EmotionGraph;

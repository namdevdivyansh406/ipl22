import React, { useState, useEffect } from 'react';
import EmotionGraph from './components/emotiongraph';
import Scoreboard from './components/scoreboard';
import { fetchEmotions, fetchMoments } from './api';
import { MessageSquare, Flame } from 'lucide-react';

function App() {
  const [emotionData, setEmotionData] = useState([]);
  const [momentsData, setMomentsData] = useState([]);
  const [loading, setLoading] = useState(true);

  // Use simple polling to get live updates every 5 seconds
  useEffect(() => {
    const loadData = async () => {
      const eData = await fetchEmotions();
      const mData = await fetchMoments();
      
      if (eData && eData.data) setEmotionData(eData.data);
      if (mData && mData.moments) setMomentsData(mData.moments);
      setLoading(false);
    };

    loadData(); // initial load
    const interval = setInterval(loadData, 5000); // poll every 5s

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="dashboard-container">
      <header className="header">
        <h1>Crowd Pulse</h1>
        <p>Real-Time Match Emotion Heatmap & Viral Moments</p>
      </header>

      <Scoreboard data={emotionData} />

      <div className="grid-layout">
        {/* Main Graph Area */}
        <div className="glass-card">
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: '1.5rem', gap: '0.5rem' }}>
            <ActivityIcon />
            <h2 style={{ margin: 0, fontSize: '1.25rem' }}>Live Emotion Graph</h2>
          </div>
          {loading ? (
            <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>Connecting to stadium...</div>
          ) : (
            <EmotionGraph data={emotionData} />
          )}
        </div>

        {/* Viral Moments Area */}
        <div className="glass-card">
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: '1.5rem', gap: '0.5rem' }}>
            <Flame color="#ef4444" />
            <h2 style={{ margin: 0, fontSize: '1.25rem' }}>Viral Moments</h2>
          </div>
          
          <div className="moments-list">
            {momentsData.length === 0 && !loading && (
              <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '1rem' }}>No viral moments yet.</div>
            )}
            
            {momentsData.map((moment, idx) => (
              <div key={idx} className={`moment-card ${moment.emotion.toLowerCase()}`}>
                <div className="moment-header">
                  <span style={{ fontWeight: 'bold', color: 'var(--text-light)' }}>@{moment.username}</span>
                  <span className={`score-badge ${moment.emotion.toLowerCase()}`} style={{ fontSize: '0.75rem', padding: '0.1rem 0.5rem' }}>
                    {moment.emotion} ({moment.score}/10)
                  </span>
                </div>
                <p className="moment-text">"{moment.text}"</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

const ActivityIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: "var(--accent-blue)" }}>
    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
  </svg>
);

export default App;

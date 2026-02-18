import React, { useState, useEffect } from 'react';
import { ArwesThemeProvider, StylesBaseline, FrameLines, Button, Text } from '@arwes/core';

// --- Custom Theme ---
const theme = {
  color: {
    primary: { base: '#D4AF37' }, // Gold
    secondary: { base: '#CD7F32' }, // Bronze
    alert: { base: '#FF4500' }, // Red-Orange
    success: { base: '#00FF41' } // Green
  }
};

const App = () => {
  return (
    <ArwesThemeProvider theme={theme}>
      <StylesBaseline />
      <div style={{ padding: '20px', backgroundColor: '#050505', minHeight: '100vh', fontFamily: 'Orbitron' }}>
        
        {/* Header */}
        <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h1 style={{ color: '#D4AF37', margin: 0 }}>🔱 OLYMPUS</h1>
          <div>
            <Button palette='primary'>MORTAL</Button>
            <Button palette='secondary'>TITAN</Button>
          </div>
        </header>

        <hr style={{ borderColor: '#CD7F32', margin: '20px 0' }} />

        {/* Triptych Layout */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr 1fr', gap: '20px' }}>
          
          {/* Left Pane: Cerberus */}
          <section>
            <FrameLines title='CERBERUS GATE'>
              <div style={{ padding: '20px' }}>
                <Text>Head 1: System Context</Text>
                <input style={{ width: '100%', background: '#111', border: '1px solid #CD7F32', color: '#fff', padding: '10px', margin: '10px 0' }} />
                <Button palette='alert' style={{ width: '100%' }}>SUMMON HEROES</Button>
              </div>
            </FrameLines>
          </section>

          {/* Center Pane: Hydra */}
          <section>
            <FrameLines title='THE BATTLEFIELD'>
              <div style={{ height: '500px', display: 'flex', alignItems: 'center', justifyItems: 'center' }}>
                <Text style={{ textAlign: 'center', width: '100%' }}>[3D HYDRA GRAPH ACTIVE]</Text>
              </div>
            </FrameLines>
          </section>

          {/* Right Pane: Augean */}
          <section>
            <FrameLines title='THE TREASURES'>
              <div style={{ padding: '20px' }}>
                <Text palette='success'>[13:42] SLAF initialized</Text>
                <Text palette='success'>[13:45] Pushed to GitHub</Text>
              </div>
            </FrameLines>
          </section>

        </div>

        {/* Footer */}
        <footer style={{ marginTop: '20px', textAlign: 'center' }}>
          <Text style={{ fontSize: '0.8em', color: '#888' }}>DJED PILLAR: STABLE | WAMPUM: SIGNED</Text>
        </footer>

      </div>
    </ArwesThemeProvider>
  );
};

export default App;

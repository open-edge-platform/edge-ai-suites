// src/App.tsx
import Header from './components/Header/Header';
import TopPanel from './components/TopPanel/TopPanel';
import Body from './components/common/Body';
import Footer from './components/Footer/Footer';
import './App.css';
import { MetricsPoller } from './components/common/MetricsPoller';

function App() {
  return (
    <div className="app">
      <MetricsPoller />
      <Header />
      <TopPanel />
      <Body />
      <Footer />
    </div>
  );
}

export default App;
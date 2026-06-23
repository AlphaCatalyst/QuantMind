import React from 'react';
import { Button } from 'antd';
import { FlaskConical, Layers, RefreshCw } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { PAGE_LAYOUT } from '../config/pageLayout';
import { BUTTON_STYLES } from '../features/research/constants';
import FactorResearchWorkbench from '../features/research/components/FactorResearchWorkbench';
import '../styles/research-next-theme.css';

const FactorResearchPage: React.FC = () => {
  const navigate = useNavigate();

  return (
    <div className={`${PAGE_LAYOUT.outerClass} research-platform-page`}>
      <div className={`${PAGE_LAYOUT.frameClass} overflow-y-auto custom-scrollbar`}>
        <header className={`${PAGE_LAYOUT.headerClass}`} style={{ height: `${PAGE_LAYOUT.headerHeight}px` }}>
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-500 via-teal-500 to-sky-400 text-white shadow-lg shadow-emerald-900/20">
              <FlaskConical className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-slate-900">因子研究</h1>
              <p className="text-[10px] font-bold uppercase tracking-[0.24em] text-slate-500">Factor Research Workspace</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button icon={<RefreshCw className="h-4 w-4" />} className={BUTTON_STYLES.headerRefresh}>
              刷新状态
            </Button>
            <Button
              icon={<Layers className="h-4 w-4" />}
              className={BUTTON_STYLES.headerSave}
              onClick={() => navigate('/model-training')}
            >
              进入模型训练
            </Button>
          </div>
        </header>

        <div className="flex-1 flex flex-col">
          <div className={`${PAGE_LAYOUT.contentOuterClass}`}>
            <FactorResearchWorkbench />
          </div>
        </div>
      </div>
    </div>
  );
};

export default FactorResearchPage;

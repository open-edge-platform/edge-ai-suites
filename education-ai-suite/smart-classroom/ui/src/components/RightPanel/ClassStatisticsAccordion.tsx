import React, { useEffect } from 'react';
import { useAppDispatch, useAppSelector } from '../../redux/hooks';
import { setClassStatistics } from '../../redux/slices/fetchClassStatistics';
import { getClassStatistics } from '../../services/api';
import Accordion from '../common/Accordion';
import { useTranslation } from 'react-i18next';
const ClassStatisticsAccordion: React.FC = () => {
  const dispatch = useAppDispatch();
  const sessionId = useAppSelector((state) => state.ui.sessionId);
  const classStatistics = useAppSelector((state) => state.classStatistics.statistics);

  useEffect(() => {
    const fetchData = async () => {
      if (sessionId) {
        try {
          const data = await getClassStatistics(sessionId);
          dispatch(setClassStatistics(data));
        } catch (error) {
          console.error('Failed to fetch class statistics:', error);
        }
      }
    };

    fetchData();
  }, [sessionId, dispatch]);

  const { t } = useTranslation();

return (
    <Accordion title={t('accordion.classStatistics')}>
      <div className="accordion-content">
        <p>
          <strong>{t('classStatistics.studentCount')}:</strong> {classStatistics.student_count}
        </p>
        <p>
          <strong>{t('classStatistics.standCount')}:</strong> {classStatistics.stand_count}
        </p>
        <p>
          <strong>{t('classStatistics.raiseUpCount')}:</strong> {classStatistics.raise_up_count}
        </p>
        <h4>{t('classStatistics.standReIdData')}:</h4>
        <ul>
          {classStatistics.stand_reid.map((entry) => (
            <li key={entry.student_id}>
              {t('classStatistics.studentId')}: {entry.student_id}, {t('classStatistics.count')}: {entry.count}
            </li>
          ))}
        </ul>
      </div>
    </Accordion>
  );
};

export default ClassStatisticsAccordion;
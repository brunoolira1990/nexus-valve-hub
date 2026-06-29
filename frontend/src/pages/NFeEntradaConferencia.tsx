import { useParams } from 'react-router-dom';
import { NFeEntradaConferenciaPanel } from '@/components/fiscal/NFeEntradaConferenciaPanel';

const NFeEntradaConferenciaPage = () => {
  const { id } = useParams();
  const nfId = Number(id);
  if (!nfId) return null;
  return <NFeEntradaConferenciaPanel nfeHistoricaId={nfId} />;
};

export default NFeEntradaConferenciaPage;

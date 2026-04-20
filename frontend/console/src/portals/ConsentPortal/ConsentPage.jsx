import { useState, useEffect } from 'react';
import { fetchConsentDetails, submitConsent } from '../../api/index';

export default function ConsentPage({ token }) {
  const [details, setDetails] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [submitted, setSubmitted] = useState(false);
  
  // Form State
  const [reports, setReports] = useState(false);
  const [photos, setPhotos] = useState(false);
  const [audio, setAudio] = useState(false);
  const [billing, setBilling] = useState(false);
  const [signature, setSignature] = useState('');
  
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const data = await fetchConsentDetails(token);
        setDetails(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [token]);

  const isValid = reports && photos && audio && billing && signature.trim().length > 2;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!isValid) return;
    
    setSubmitting(true);
    setError(null);
    try {
      await submitConsent(token, {
        consent_daily_reports: reports,
        consent_photos: photos,
        consent_audio_processing: audio,
        consent_billing_data: billing,
        digital_signature: signature.trim()
      });
      setSubmitted(true);
    } catch (err) {
      setError(err.message);
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-surface flex flex-col items-center justify-center -mt-10">
        <div className="spinner mb-4" />
        <p className="text-on-surface-variant text-sm font-medium">Loading secure portal...</p>
      </div>
    );
  }

  if (error && !details) {
    return (
      <div className="min-h-screen bg-surface px-6 pt-24 max-w-lg mx-auto text-center">
        <span className="material-symbols-outlined text-error text-5xl mb-4">error</span>
        <h2 className="font-headline text-2xl mb-2 text-on-surface">Link Unavailable</h2>
        <p className="text-on-surface-variant text-sm bg-surface-container py-3 px-4 rounded-xl inline-block text-left shadow-ambient">
          {error}
        </p>
      </div>
    );
  }

  if (details?.is_used || submitted) {
    return (
      <div className="min-h-screen bg-surface px-6 pt-32 max-w-lg mx-auto text-center card-appear">
        <div className="w-20 h-20 bg-[#e8f5e9] rounded-full flex items-center justify-center mx-auto mb-6 shadow-ambient">
          <span className="material-symbols-outlined text-4xl text-[#2e7d32]" style={{ fontVariationSettings: "'FILL' 1" }}>
            check_circle
          </span>
        </div>
        <h2 className="font-headline text-3xl font-semibold mb-3 text-on-surface tracking-tight">You're all set!</h2>
        <p className="text-on-surface-variant text-base max-w-sm mx-auto leading-relaxed">
          Thank you for completing the setup for <span className="font-medium text-on-surface">{details?.child_first_name || 'your child'}</span>. You can now close this window or return to the Parent Portal.
        </p>
      </div>
    );
  }

  if (details?.is_expired) {
    return (
      <div className="min-h-screen bg-surface px-6 pt-24 max-w-lg mx-auto text-center">
        <span className="material-symbols-outlined text-on-surface-variant text-5xl mb-4">history</span>
        <h2 className="font-headline text-2xl mb-2 text-on-surface">Link Expired</h2>
        <p className="text-on-surface-variant text-sm">
          This setup link has expired for security reasons. Please ask your center director to resend the link.
        </p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-surface pb-32">
      {/* Immersive Header */}
      <div className="bg-primary/5 pt-16 pb-12 px-6 border-b border-primary/10 rounded-b-[2.5rem] shadow-ambient">
        <div className="max-w-lg mx-auto text-center">
          <p className="text-sm font-semibold tracking-wider uppercase text-primary mb-2">
            {details.center_name}
          </p>
          <h1 className="font-headline text-3xl font-bold tracking-tight text-on-surface mb-3 leading-tight">
            Setting up <span className="text-primary">{details.child_first_name}</span>'s profile
          </h1>
          <p className="text-on-surface-variant text-sm max-w-md mx-auto leading-relaxed">
            To provide you with secure, real-time updates and daily recaps, we need your consent to process updates for your child.
          </p>
        </div>
      </div>

      <div className="px-6 -mt-6">
        <div className="max-w-xl mx-auto">
          {error && (
            <div className="mb-6 flex items-center gap-3 bg-error-container text-on-error-container px-5 py-4 rounded-xl shadow-ambient card-appear">
              <span className="material-symbols-outlined text-xl">warning</span>
              <span className="text-sm font-medium">{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6 card-appear" style={{ animationDelay: '0.1s' }}>
            
            {/* Required Permissions Section */}
            <div className="glass-panel p-6 rounded-2xl shadow-ambient space-y-5">
              <div className="flex items-center gap-2 border-b border-outline-variant/30 pb-4 mb-2">
                <span className="material-symbols-outlined text-primary text-xl">shield_locked</span>
                <h3 className="font-headline text-lg font-semibold text-on-surface">Privacy & Permissions</h3>
              </div>

              <Checkbox 
                id="reports" 
                checked={reports} 
                onChange={setReports}
                title="Daily Reports & Logs"
                desc={`I consent to Affirmi generating and storing daily reports, logs, and milestone records for ${details.child_first_name}.`}
              />
              <Checkbox 
                id="photos" 
                checked={photos} 
                onChange={setPhotos}
                title="Photos & Media"
                desc="I consent to the secure storage and processing of photos taken by teachers exclusively for sharing with me."
              />
              <Checkbox 
                id="audio" 
                checked={audio} 
                onChange={setAudio}
                title="Audio Processing"
                desc="I consent to the processing of teacher voice memos by Affirmi to structure updates. I understand these are never used for AI training and are deleted immediately after processing."
              />
              <Checkbox 
                id="billing" 
                checked={billing} 
                onChange={setBilling}
                title="Billing & Attendance"
                desc="I consent to the tracking of attendance and billing-related events (e.g. late pickups) strictly for invoicing purposes by the center."
              />
            </div>

            {/* Signature Section */}
            <div className="glass-panel p-6 rounded-2xl shadow-ambient">
              <label htmlFor="signature" className="block mb-2 font-medium text-on-surface">Digital Signature</label>
              <p className="text-xs text-on-surface-variant mb-4">
                By typing your full name below, you confirm you are the parent or legal guardian of {details.child_first_name} and agree to the above terms.
              </p>
              <input 
                id="signature"
                type="text" 
                placeholder="E.g., Jane Doe"
                className="w-full bg-surface text-on-surface px-4 py-3 rounded-xl border border-outline-variant focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-shadow"
                value={signature}
                onChange={(e) => setSignature(e.target.value)}
                required
                disabled={submitting}
              />
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={!isValid || submitting}
              className={`w-full py-4 rounded-xl font-semibold text-base tracking-wide transition-all duration-300 shadow-ambient flex justify-center items-center gap-2 ${
                isValid && !submitting
                  ? 'bg-primary text-on-primary hover:bg-primary/95 active:scale-[0.98]'
                  : 'bg-surface-container-highest text-on-surface-variant/50 cursor-not-allowed'
              }`}
            >
              {submitting ? (
                <>
                  <span className="material-symbols-outlined animate-spin text-lg">progress_activity</span>
                  Processing...
                </>
              ) : (
                'Accept & Complete Setup'
              )}
            </button>
            <p className="text-center text-[10px] text-on-surface-variant uppercase tracking-widest mt-4">
              Protected by Affirmi Security
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}

function Checkbox({ id, checked, onChange, title, desc }) {
  return (
    <div className="flex items-start gap-4 p-2 rounded-xl hover:bg-surface-container/50 transition-colors">
      <div className="flex-shrink-0 pt-1">
        <button
          type="button"
          role="checkbox"
          aria-checked={checked}
          onClick={() => onChange(!checked)}
          className={`w-6 h-6 rounded flex items-center justify-center transition-all ${
            checked 
              ? 'bg-primary border-primary text-on-primary' 
              : 'border-2 border-outline-variant bg-surface'
          }`}
        >
          {checked && <span className="material-symbols-outlined text-[18px] font-bold">check</span>}
        </button>
      </div>
      <div>
        <label htmlFor={id} className="font-medium text-sm text-on-surface cursor-pointer select-none" onClick={() => onChange(!checked)}>
          {title}
        </label>
        <p className="text-xs text-on-surface-variant mt-1 leading-relaxed cursor-pointer select-none" onClick={() => onChange(!checked)}>
          {desc}
        </p>
      </div>
    </div>
  );
}

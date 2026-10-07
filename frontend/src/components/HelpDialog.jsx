import { Dialog } from './ui.jsx'

// Short, task-based help written for each type of user (HCI: help and documentation).
const HELP = {
  TEACHER: {
    intro: 'Taking attendance takes four steps:',
    steps: [
      'Open your class and press "Take attendance".',
      'Take 1–10 photos of the class with your phone or laptop camera, or choose photos you already took.',
      'Press "Check attendance" and wait a few seconds.',
      'Look at the list. Choose Present or Absent for anyone marked "Not sure", then press "Save attendance".',
    ],
    faqs: [
      ['What does "Not sure" mean?', 'The face was unclear or looked similar to someone else. SnapClass never guesses: you decide.'],
      ['A student is marked wrong. What do I do?', 'Before saving, just press Present or Absent. After saving, press "Change" and write a short reason.'],
      ['How do students join my class?', 'Open the class, go to "Students" and create an invite link. Show the QR code on the projector or share the link.'],
      ['A student has no face set up.', 'They appear with the note "Mark by hand". Choose Present or Absent for them yourself.'],
      [
        'Some students were not found. Can I add more photos?',
        'Yes, any time before saving. On the review screen press "Add or change photos", add photos (or remove an unclear one) and press "Check again". Your Present/Absent choices are kept.',
      ],
      [
        'A student is in class but is never recognised.',
        'Mark them Present by hand, then press "Ask for new face photo". They will be asked to upload a new photo when they sign in. Until they do, SnapClass will not mark them present automatically.',
      ],
    ],
  },
  STUDENT: {
    intro: 'Getting set up takes about two minutes:',
    steps: [
      "Create your account with your student ID, full name and a password (or open your teacher's invite link).",
      'Join each subject by scanning the QR code or opening the invite link your teacher shares.',
      'Open "Face setup" and read the permission text. Press "I agree" if you are happy with it.',
      'Take 3–5 clear photos of your face (good light, only you, looking at the camera).',
      'Optional: record your voice three times.',
    ],
    faqs: [
      ['Are my photos stored?', 'No. Your setup photos are deleted right after processing. Only a numeric face code is kept, and it is never shown to anyone.'],
      ['Can I remove my data?', 'Yes, at any time: "Face setup" → "Remove my face and voice data". Your teacher will then mark you by hand.'],
      ['My attendance looks wrong.', 'Please talk to your teacher. They can correct it, and every correction is recorded.'],
      [
        'My teacher asked for a new face photo.',
        'Open "Face setup" and take 3–5 new photos. Until you do, you will not be marked present automatically in any lecture.',
      ],
    ],
  },
  ADMIN: {
    intro: 'As an administrator you can:',
    steps: [
      'Add teacher accounts and turn accounts off when someone leaves.',
      'Watch the system: failed jobs and waiting jobs are shown at the top of the dashboard.',
      'Change how long class photos are kept, and (for technical staff) the matching settings.',
      'Read the activity history: every saved attendance, correction and data removal is recorded.',
    ],
    faqs: [
      ['Should I change the matching settings?', 'Only after measuring accuracy with the evaluation script. Wrong values can mark students present by mistake.'],
      ['A teacher forgot their password.', 'Password reset is not available in this version yet. Contact the technical team that runs SnapClass.'],
    ],
  },
}

export default function HelpDialog({ open, onClose, role }) {
  const help = HELP[role] || HELP.TEACHER
  return (
    <Dialog open={open} title="How SnapClass works" onClose={onClose}>
      <p className="muted">{help.intro}</p>
      <ol className="help-steps">
        {help.steps.map((step) => (
          <li key={step}>{step}</li>
        ))}
      </ol>
      <h4 className="help-subtitle">Common questions</h4>
      {help.faqs.map(([question, answer]) => (
        <details key={question} className="faq">
          <summary>{question}</summary>
          <p className="muted">{answer}</p>
        </details>
      ))}
      <div className="dialog-actions">
        <button type="button" className="btn btn-primary" onClick={onClose}>
          Got it
        </button>
      </div>
    </Dialog>
  )
}

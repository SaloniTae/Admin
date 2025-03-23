// pages/index.tsx
import React, { useEffect, useState, ChangeEvent } from "react";
import {
  Container,
  Card,
  Text,
  Input,
  Spacer,
  Switch,
} from "@nextui-org/react";
import firebase from "firebase/compat/app";
import "firebase/compat/database";

// Replace with your actual Firebase config values.
const firebaseConfig = {
        apiKey: "AIzaSyA02dPt8yMTSmhzyj9PIrm4UlWr1a1waD4",
        authDomain: "testing-6de54.firebaseapp.com",
        databaseURL: "https://testing-6de54-default-rtdb.firebaseio.com",
        projectId: "testing-6de54",
        storageBucket: "testing-6de54.firebasestorage.app",
        messagingSenderId: "159795986690",
        appId: "1:159795986690:web:2e4de44d725826dc01821b"
};

if (!firebase.apps.length) {
  firebase.initializeApp(firebaseConfig);
}
const db = firebase.database();

// A reusable component for dashboard sections.
interface DashboardSectionProps {
  title: string;
  children: React.ReactNode;
}

const DashboardSection: React.FC<DashboardSectionProps> = ({ title, children }) => (
  <Card css={{ mw: "100%", p: "$10", mb: "$10" }}>
    <Card.Header>
      <Text h3>{title}</Text>
    </Card.Header>
    <Card.Body>{children}</Card.Body>
  </Card>
);

// -------------------- ADMIN CONFIG --------------------
const AdminConfig: React.FC = () => {
  const [inferiorAdmins, setInferiorAdmins] = useState<string[]>([]);
  const [superiorAdmins, setSuperiorAdmins] = useState<string[]>([]);

  useEffect(() => {
    const ref = db.ref("admin_config");
    ref.on("value", (snapshot) => {
      const data = snapshot.val() || {};
      setInferiorAdmins(data.inferior_admins || []);
      setSuperiorAdmins(data.superior_admins || []);
    });
  }, []);

  const updateField = (field: string, value: any) => {
    db.ref("admin_config").update({ [field]: value });
  };

  return (
    <DashboardSection title="Admin Config">
      <Text>Inferior Admins (comma‑separated):</Text>
      <Input
        fullWidth
        initialValue={inferiorAdmins.join(",")}
        onBlur={(e: ChangeEvent<HTMLInputElement>) => {
          const arr = e.target.value
            .split(",")
            .map((s) => s.trim())
            .filter((s) => s !== "");
          updateField("inferior_admins", arr);
        }}
      />
      <Spacer y={1} />
      <Text>Superior Admins (comma‑separated):</Text>
      <Input
        fullWidth
        initialValue={superiorAdmins.join(",")}
        onBlur={(e: ChangeEvent<HTMLInputElement>) => {
          const arr = e.target.value
            .split(",")
            .map((s) => s.trim())
            .filter((s) => s !== "");
          updateField("superior_admins", arr);
        }}
      />
    </DashboardSection>
  );
};

// -------------------- CREDENTIALS --------------------
interface Credential {
  belongs_to_slot: string;
  email: string;
  expiry_date: string;
  password: string;
  max_usage: number;
  usage_count: number;
  locked: number;
}

interface CredentialCardProps {
  credKey: string;
}

const CredentialCard: React.FC<CredentialCardProps> = ({ credKey }) => {
  const [cred, setCred] = useState<Credential | null>(null);

  useEffect(() => {
    const ref = db.ref(credKey);
    ref.on("value", (snapshot) => {
      setCred(snapshot.val());
    });
  }, [credKey]);

  const updateField = (field: keyof Credential, value: any) => {
    db.ref(`${credKey}/${field}`).set(value);
  };

  if (!cred) return <Text>Loading {credKey}...</Text>;

  return (
    <DashboardSection title={`Credential: ${credKey}`}>
      <Input
        fullWidth
        label="Belongs To Slot"
        initialValue={cred.belongs_to_slot}
        onBlur={(e: ChangeEvent<HTMLInputElement>) => updateField("belongs_to_slot", e.target.value)}
      />
      <Spacer y={0.5} />
      <Input
        fullWidth
        label="Email"
        initialValue={cred.email}
        onBlur={(e: ChangeEvent<HTMLInputElement>) => updateField("email", e.target.value)}
      />
      <Spacer y={0.5} />
      <Input
        fullWidth
        label="Expiry Date"
        initialValue={cred.expiry_date}
        onBlur={(e: ChangeEvent<HTMLInputElement>) => updateField("expiry_date", e.target.value)}
      />
      <Spacer y={0.5} />
      <Input
        fullWidth
        label="Password"
        initialValue={cred.password}
        onBlur={(e: ChangeEvent<HTMLInputElement>) => updateField("password", e.target.value)}
      />
      <Spacer y={0.5} />
      <Input
        fullWidth
        type="number"
        label="Max Usage"
        initialValue={cred.max_usage.toString()}
        onBlur={(e: ChangeEvent<HTMLInputElement>) => updateField("max_usage", parseInt(e.target.value))}
      />
      <Spacer y={0.5} />
      <Input
        fullWidth
        type="number"
        label="Usage Count"
        initialValue={cred.usage_count.toString()}
        onBlur={(e: ChangeEvent<HTMLInputElement>) => updateField("usage_count", parseInt(e.target.value))}
      />
      <Spacer y={0.5} />
      <Input
        fullWidth
        type="number"
        label="Locked (0 or 1)"
        initialValue={cred.locked.toString()}
        onBlur={(e: ChangeEvent<HTMLInputElement>) => updateField("locked", parseInt(e.target.value))}
      />
    </DashboardSection>
  );
};

// -------------------- FREE TRIAL CLAIMS --------------------
const FreeTrialClaims: React.FC = () => {
  const [claims, setClaims] = useState<{ [key: string]: boolean }>({});

  useEffect(() => {
    const ref = db.ref("free_trial_claims");
    ref.on("value", (snapshot) => {
      setClaims(snapshot.val() || {});
    });
  }, []);

  const toggleClaim = (claimId: string, current: boolean) => {
    db.ref(`free_trial_claims/${claimId}`).set(!current);
  };

  return (
    <DashboardSection title="Free Trial Claims">
      {Object.entries(claims).map(([key, value]) => (
        <div key={key} style={{ marginBottom: "0.5rem" }}>
          <Text>{key}</Text>
          <Switch checked={value} onChange={() => toggleClaim(key, value)} />
        </div>
      ))}
    </DashboardSection>
  );
};

// -------------------- REFERRAL SETTINGS --------------------
const ReferralSettings: React.FC = () => {
  const [settings, setSettings] = useState<any>({});

  useEffect(() => {
    const ref = db.ref("referral_settings");
    ref.on("value", (snapshot) => {
      setSettings(snapshot.val() || {});
    });
  }, []);

  const updateField = (field: string, value: any) => {
    db.ref("referral_settings").update({ [field]: value });
  };

  return (
    <DashboardSection title="Referral Settings">
      <div style={{ marginBottom: "0.5rem" }}>
        <Text>Buy With Points Enabled:</Text>
        <Switch
          checked={settings.buy_with_points_enabled || false}
          onChange={(e) => updateField("buy_with_points_enabled", e.target.checked)}
        />
      </div>
      <Spacer y={0.5} />
      <div style={{ marginBottom: "0.5rem" }}>
        <Text>Free Trial Enabled:</Text>
        <Switch
          checked={settings.free_trial_enabled || false}
          onChange={(e) => updateField("free_trial_enabled", e.target.checked)}
        />
      </div>
      <Spacer y={0.5} />
      <Input
        fullWidth
        label="Points Per Referral"
        initialValue={settings.points_per_referral?.toString() || ""}
        onBlur={(e: ChangeEvent<HTMLInputElement>) => updateField("points_per_referral", parseInt(e.target.value))}
      />
      <Spacer y={0.5} />
      <Input
        fullWidth
        label="Required Point"
        initialValue={settings.required_point?.toString() || ""}
        onBlur={(e: ChangeEvent<HTMLInputElement>) => updateField("required_point", parseInt(e.target.value))}
      />
    </DashboardSection>
  );
};

// -------------------- REFERRALS --------------------
const ReferralsSection: React.FC = () => {
  const [referrals, setReferrals] = useState<any>({});

  useEffect(() => {
    const ref = db.ref("referrals");
    ref.on("value", (snapshot) => {
      setReferrals(snapshot.val() || {});
    });
  }, []);

  const updateReferrals = (newData: any) => {
    db.ref("referrals").set(newData);
  };

  return (
    <DashboardSection title="Referrals">
      <Text>
        (Edit the referrals as JSON. For production, build a dedicated form.)
      </Text>
      <Input
        fullWidth
        type="textarea"
        initialValue={JSON.stringify(referrals, null, 2)}
        onBlur={(e: ChangeEvent<HTMLTextAreaElement>) => {
          try {
            const parsed = JSON.parse(e.target.value);
            updateReferrals(parsed);
          } catch (err) {
            alert("Invalid JSON format");
          }
        }}
      />
    </DashboardSection>
  );
};

// -------------------- SETTINGS: SLOTS --------------------
const SlotsSection: React.FC = () => {
  const [slots, setSlots] = useState<any>({});

  useEffect(() => {
    const ref = db.ref("settings/slots");
    ref.on("value", (snapshot) => {
      setSlots(snapshot.val() || {});
    });
  }, []);

  const updateSlotField = (slotKey: string, field: string, value: any) => {
    db.ref(`settings/slots/${slotKey}`).update({ [field]: value });
  };

  return (
    <DashboardSection title="Settings - Slots">
      {Object.entries(slots).map(([slotKey, slot]: [string, any]) => (
        <Card key={slotKey} css={{ mw: "100%", p: "$8", mb: "$8" }}>
          <Card.Header>
            <Text h4>{slotKey}</Text>
          </Card.Header>
          <Card.Body>
            <div style={{ marginBottom: "0.5rem" }}>
              <Text>Enabled:</Text>
              <Switch
                checked={slot.enabled}
                onChange={(e) =>
                  updateSlotField(slotKey, "enabled", e.target.checked)
                }
              />
            </div>
            <Spacer y={0.5} />
            <Input
              fullWidth
              label="Frequency"
              initialValue={slot.frequency || ""}
              onBlur={(e: ChangeEvent<HTMLInputElement>) =>
                updateSlotField(slotKey, "frequency", e.target.value)
              }
            />
            <Spacer y={0.5} />
            <Input
              fullWidth
              label="Last Update"
              initialValue={slot.last_update || ""}
              onBlur={(e: ChangeEvent<HTMLInputElement>) =>
                updateSlotField(slotKey, "last_update", e.target.value)
              }
            />
            <Spacer y={0.5} />
            <Input
              fullWidth
              type="number"
              label="Required Amount"
              initialValue={slot.required_amount?.toString() || ""}
              onBlur={(e: ChangeEvent<HTMLInputElement>) =>
                updateSlotField(slotKey, "required_amount", parseInt(e.target.value))
              }
            />
            <Spacer y={0.5} />
            <Input
              fullWidth
              label="Slot Start"
              initialValue={slot.slot_start || ""}
              onBlur={(e: ChangeEvent<HTMLInputElement>) =>
                updateSlotField(slotKey, "slot_start", e.target.value)
              }
            />
            <Spacer y={0.5} />
            <Input
              fullWidth
              label="Slot End"
              initialValue={slot.slot_end || ""}
              onBlur={(e: ChangeEvent<HTMLInputElement>) =>
                updateSlotField(slotKey, "slot_end", e.target.value)
              }
            />
          </Card.Body>
        </Card>
      ))}
    </DashboardSection>
  );
};

// -------------------- TRANSACTIONS --------------------
const TransactionsSection: React.FC = () => {
  const [transactions, setTransactions] = useState<any>({});

  useEffect(() => {
    const ref = db.ref("transactions");
    ref.on("value", (snapshot) => {
      setTransactions(snapshot.val() || {});
    });
  }, []);

  const updateTransactions = (newData: any) => {
    db.ref("transactions").set(newData);
  };

  return (
    <DashboardSection title="Transactions">
      <Text>
        (Edit the transactions as JSON. For production, build a dedicated interface.)
      </Text>
      <Input
        fullWidth
        type="textarea"
        initialValue={JSON.stringify(transactions, null, 2)}
        onBlur={(e: ChangeEvent<HTMLTextAreaElement>) => {
          try {
            const parsed = JSON.parse(e.target.value);
            updateTransactions(parsed);
          } catch (err) {
            alert("Invalid JSON format");
          }
        }}
      />
    </DashboardSection>
  );
};

// -------------------- UI CONFIG --------------------
const UIConfigSection: React.FC = () => {
  const [uiConfig, setUIConfig] = useState<any>({});

  useEffect(() => {
    const ref = db.ref("ui_config");
    ref.on("value", (snapshot) => {
      setUIConfig(snapshot.val() || {});
    });
  }, []);

  const updateFlowField = (flow: string, field: string, value: any) => {
    db.ref(`ui_config/${flow}`).update({ [field]: value });
  };

  return (
    <DashboardSection title="UI Config">
      {/* Approve Flow */}
      <Card css={{ mw: "100%", p: "$8", mb: "$8" }}>
        <Card.Header>
          <Text h4>Approve Flow</Text>
        </Card.Header>
        <Card.Body>
          <Input
            fullWidth
            label="Account Format"
            initialValue={uiConfig.approve_flow?.account_format || ""}
            onBlur={(e: ChangeEvent<HTMLInputElement>) =>
              updateFlowField("approve_flow", "account_format", e.target.value)
            }
          />
          <Spacer y={0.5} />
          <Input
            fullWidth
            label="Gif URL"
            initialValue={uiConfig.approve_flow?.gif_url || ""}
            onBlur={(e: ChangeEvent<HTMLInputElement>) =>
              updateFlowField("approve_flow", "gif_url", e.target.value)
            }
          />
          <Spacer y={0.5} />
          <Input
            fullWidth
            label="Success Text"
            initialValue={uiConfig.approve_flow?.success_text || ""}
            onBlur={(e: ChangeEvent<HTMLInputElement>) =>
              updateFlowField("approve_flow", "success_text", e.target.value)
            }
          />
        </Card.Body>
      </Card>
      {/* Confirmation Flow */}
      <Card css={{ mw: "100%", p: "$8", mb: "$8" }}>
        <Card.Header>
          <Text h4>Confirmation Flow</Text>
        </Card.Header>
        <Card.Body>
          <Input
            fullWidth
            label="Button Text"
            initialValue={uiConfig.confirmation_flow?.button_text || ""}
            onBlur={(e: ChangeEvent<HTMLInputElement>) =>
              updateFlowField("confirmation_flow", "button_text", e.target.value)
            }
          />
          <Spacer y={0.5} />
          <Input
            fullWidth
            label="Callback Data"
            initialValue={uiConfig.confirmation_flow?.callback_data || ""}
            onBlur={(e: ChangeEvent<HTMLInputElement>) =>
              updateFlowField("confirmation_flow", "callback_data", e.target.value)
            }
          />
          <Spacer y={0.5} />
          <Input
            fullWidth
            label="Caption"
            initialValue={uiConfig.confirmation_flow?.caption || ""}
            onBlur={(e: ChangeEvent<HTMLInputElement>) =>
              updateFlowField("confirmation_flow", "caption", e.target.value)
            }
          />
          <Spacer y={0.5} />
          <Input
            fullWidth
            label="Gif URL"
            initialValue={uiConfig.confirmation_flow?.gif_url || ""}
            onBlur={(e: ChangeEvent<HTMLInputElement>) =>
              updateFlowField("confirmation_flow", "gif_url", e.target.value)
            }
          />
          <Spacer y={0.5} />
          <Input
            fullWidth
            label="Photo URL"
            initialValue={uiConfig.confirmation_flow?.photo_url || ""}
            onBlur={(e: ChangeEvent<HTMLInputElement>) =>
              updateFlowField("confirmation_flow", "photo_url", e.target.value)
            }
          />
        </Card.Body>
      </Card>
      {/* Crunchyroll Screen */}
      <Card css={{ mw: "100%", p: "$8", mb: "$8" }}>
        <Card.Header>
          <Text h4>Crunchyroll Screen</Text>
        </Card.Header>
        <Card.Body>
          <Input
            fullWidth
            label="Button Text"
            initialValue={uiConfig.crunchyroll_screen?.button_text || ""}
            onBlur={(e: ChangeEvent<HTMLInputElement>) =>
              updateFlowField("crunchyroll_screen", "button_text", e.target.value)
            }
          />
          <Spacer y={0.5} />
          <Input
            fullWidth
            label="Callback Data"
            initialValue={uiConfig.crunchyroll_screen?.callback_data || ""}
            onBlur={(e: ChangeEvent<HTMLInputElement>) =>
              updateFlowField("crunchyroll_screen", "callback_data", e.target.value)
            }
          />
          <Spacer y={0.5} />
          <Input
            fullWidth
            label="Caption"
            initialValue={uiConfig.crunchyroll_screen?.caption || ""}
            onBlur={(e: ChangeEvent<HTMLInputElement>) =>
              updateFlowField("crunchyroll_screen", "caption", e.target.value)
            }
          />
          <Spacer y={0.5} />
          <Input
            fullWidth
            label="Photo URL"
            initialValue={uiConfig.crunchyroll_screen?.photo_url || ""}
            onBlur={(e: ChangeEvent<HTMLInputElement>) =>
              updateFlowField("crunchyroll_screen", "photo_url", e.target.value)
            }
          />
        </Card.Body>
      </Card>
      {/* Freetrial Info */}
      <Card css={{ mw: "100%", p: "$8", mb: "$8" }}>
        <Card.Header>
          <Text h4>Freetrial Info</Text>
        </Card.Header>
        <Card.Body>
          <Input
            fullWidth
            label="Photo URL"
            initialValue={uiConfig.freetrial_info?.photo_url || ""}
            onBlur={(e: ChangeEvent<HTMLInputElement>) =>
              updateFlowField("freetrial_info", "photo_url", e.target.value)
            }
          />
        </Card.Body>
      </Card>
      {/* Locked Flow */}
      <Card css={{ mw: "100%", p: "$8", mb: "$8" }}>
        <Card.Header>
          <Text h4>Locked Flow</Text>
        </Card.Header>
        <Card.Body>
          <Input
            fullWidth
            label="Locked Text"
            initialValue={uiConfig.locked_flow?.locked_text || ""}
            onBlur={(e: ChangeEvent<HTMLInputElement>) =>
              updateFlowField("locked_flow", "locked_text", e.target.value)
            }
          />
        </Card.Body>
      </Card>
      {/* Out Of Stock */}
      <Card css={{ mw: "100%", p: "$8", mb: "$8" }}>
        <Card.Header>
          <Text h4>Out Of Stock</Text>
        </Card.Header>
        <Card.Body>
          <Input
            fullWidth
            label="Gif URL"
            initialValue={uiConfig.out_of_stock?.gif_url || ""}
            onBlur={(e: ChangeEvent<HTMLInputElement>) =>
              updateFlowField("out_of_stock", "gif_url", e.target.value)
            }
          />
          <Spacer y={0.5} />
          <Input
            fullWidth
            type="textarea"
            label="Messages (comma separated)"
            initialValue={(uiConfig.out_of_stock?.messages || []).join(", ")}
            onBlur={(e: ChangeEvent<HTMLInputElement>) => {
              const arr = e.target.value
                .split(",")
                .map((s) => s.trim())
                .filter((s) => s !== "");
              updateFlowField("out_of_stock", "messages", arr);
            }}
          />
        </Card.Body>
      </Card>
      {/* PhonePe Screen */}
      <Card css={{ mw: "100%", p: "$8", mb: "$8" }}>
        <Card.Header>
          <Text h4>PhonePe Screen</Text>
        </Card.Header>
        <Card.Body>
          <Input
            fullWidth
            label="Caption"
            initialValue={uiConfig.phonepe_screen?.caption || ""}
            onBlur={(e: ChangeEvent<HTMLInputElement>) =>
              updateFlowField("phonepe_screen", "caption", e.target.value)
            }
          />
          <Spacer y={0.5} />
          <Input
            fullWidth
            label="Followup Text"
            initialValue={uiConfig.phonepe_screen?.followup_text || ""}
            onBlur={(e: ChangeEvent<HTMLInputElement>) =>
              updateFlowField("phonepe_screen", "followup_text", e.target.value)
            }
          />
          <Spacer y={0.5} />
          <Input
            fullWidth
            label="Photo URL"
            initialValue={uiConfig.phonepe_screen?.photo_url || ""}
            onBlur={(e: ChangeEvent<HTMLInputElement>) =>
              updateFlowField("phonepe_screen", "photo_url", e.target.value)
            }
          />
        </Card.Body>
      </Card>
      {/* Referral Info */}
      <Card css={{ mw: "100%", p: "$8", mb: "$8" }}>
        <Card.Header>
          <Text h4>Referral Info</Text>
        </Card.Header>
        <Card.Body>
          <Input
            fullWidth
            label="Photo URL"
            initialValue={uiConfig.referral_info?.photo_url || ""}
            onBlur={(e: ChangeEvent<HTMLInputElement>) =>
              updateFlowField("referral_info", "photo_url", e.target.value)
            }
          />
        </Card.Body>
      </Card>
      {/* Reject Flow */}
      <Card css={{ mw: "100%", p: "$8", mb: "$8" }}>
        <Card.Header>
          <Text h4>Reject Flow</Text>
        </Card.Header>
        <Card.Body>
          <Input
            fullWidth
            label="Error Text"
            initialValue={uiConfig.reject_flow?.error_text || ""}
            onBlur={(e: ChangeEvent<HTMLInputElement>) =>
              updateFlowField("reject_flow", "error_text", e.target.value)
            }
          />
          <Spacer y={0.5} />
          <Input
            fullWidth
            label="Gif URL"
            initialValue={uiConfig.reject_flow?.gif_url || ""}
            onBlur={(e: ChangeEvent<HTMLInputElement>) =>
              updateFlowField("reject_flow", "gif_url", e.target.value)
            }
          />
        </Card.Body>
      </Card>
      {/* Slot Booking */}
      <Card css={{ mw: "100%", p: "$8", mb: "$8" }}>
        <Card.Header>
          <Text h4>Slot Booking</Text>
        </Card.Header>
        <Card.Body>
          <Input
            fullWidth
            label="Button Format"
            initialValue={uiConfig.slot_booking?.button_format || ""}
            onBlur={(e: ChangeEvent<HTMLInputElement>) =>
              updateFlowField("slot_booking", "button_format", e.target.value)
            }
          />
          <Spacer y={0.5} />
          <Input
            fullWidth
            label="Callback Data"
            initialValue={uiConfig.slot_booking?.callback_data || ""}
            onBlur={(e: ChangeEvent<HTMLInputElement>) =>
              updateFlowField("slot_booking", "callback_data", e.target.value)
            }
          />
          <Spacer y={0.5} />
          <Input
            fullWidth
            label="Caption"
            initialValue={uiConfig.slot_booking?.caption || ""}
            onBlur={(e: ChangeEvent<HTMLInputElement>) =>
              updateFlowField("slot_booking", "caption", e.target.value)
            }
          />
          <Spacer y={0.5} />
          <Input
            fullWidth
            label="Gif URL"
            initialValue={uiConfig.slot_booking?.gif_url || ""}
            onBlur={(e: ChangeEvent<HTMLInputElement>) =>
              updateFlowField("slot_booking", "gif_url", e.target.value)
            }
          />
          <Spacer y={0.5} />
          <Input
            fullWidth
            label="Photo URL"
            initialValue={uiConfig.slot_booking?.photo_url || ""}
            onBlur={(e: ChangeEvent<HTMLInputElement>) =>
              updateFlowField("slot_booking", "photo_url", e.target.value)
            }
          />
        </Card.Body>
      </Card>
      {/* Start Command */}
      <Card css={{ mw: "100%", p: "$8", mb: "$8" }}>
        <Card.Header>
          <Text h4>Start Command</Text>
        </Card.Header>
        <Card.Body>
          <Input
            fullWidth
            label="Welcome Text"
            initialValue={uiConfig.start_command?.welcome_text || ""}
            onBlur={(e: ChangeEvent<HTMLInputElement>) =>
              updateFlowField("start_command", "welcome_text", e.target.value)
            }
          />
          <Spacer y={0.5} />
          <Input
            fullWidth
            label="Welcome Photo URL"
            initialValue={uiConfig.start_command?.welcome_photo || ""}
            onBlur={(e: ChangeEvent<HTMLInputElement>) =>
              updateFlowField("start_command", "welcome_photo", e.target.value)
            }
          />
          <Spacer y={0.5} />
          <Input
            fullWidth
            type="textarea"
            label="Buttons (as JSON array)"
            initialValue={JSON.stringify(uiConfig.start_command?.buttons || [], null, 2)}
            onBlur={(e: ChangeEvent<HTMLTextAreaElement>) => {
              try {
                const parsed = JSON.parse(e.target.value);
                updateFlowField("start_command", "buttons", parsed);
              } catch (err) {
                alert("Invalid JSON format for buttons");
              }
            }}
          />
        </Card.Body>
      </Card>
    </DashboardSection>
  );
};

// -------------------- USED ORDER IDS --------------------
const UsedOrderIds: React.FC = () => {
  const [orderIds, setOrderIds] = useState<any>({});

  useEffect(() => {
    const ref = db.ref("used_orderids");
    ref.on("value", (snapshot) => {
      setOrderIds(snapshot.val() || {});
    });
  }, []);

  const updateOrderIds = (newData: any) => {
    db.ref("used_orderids").set(newData);
  };

  return (
    <DashboardSection title="Used Order IDs">
      <Input
        fullWidth
        type="textarea"
        label="Used Order IDs (JSON Object)"
        initialValue={JSON.stringify(orderIds, null, 2)}
        onBlur={(e: ChangeEvent<HTMLTextAreaElement>) => {
          try {
            const parsed = JSON.parse(e.target.value);
            updateOrderIds(parsed);
          } catch (err) {
            alert("Invalid JSON format");
          }
        }}
      />
    </DashboardSection>
  );
};

// -------------------- USERS --------------------
const UsersSection: React.FC = () => {
  const [users, setUsers] = useState<any>({});

  useEffect(() => {
    const ref = db.ref("users");
    ref.on("value", (snapshot) => {
      setUsers(snapshot.val() || {});
    });
  }, []);

  const updateUsers = (newData: any) => {
    db.ref("users").set(newData);
  };

  return (
    <DashboardSection title="Users">
      <Input
        fullWidth
        type="textarea"
        label="Users (JSON Object)"
        initialValue={JSON.stringify(users, null, 2)}
        onBlur={(e: ChangeEvent<HTMLTextAreaElement>) => {
          try {
            const parsed = JSON.parse(e.target.value);
            updateUsers(parsed);
          } catch (err) {
            alert("Invalid JSON format");
          }
        }}
      />
    </DashboardSection>
  );
};

// -------------------- DASHBOARD --------------------
const Dashboard: React.FC = () => {
  return (
    <Container css={{ p: "$10", mw: "1000px" }}>
      <Text h1 css={{ textAlign: "center", mb: "$10" }}>
        Firebase Admin Dashboard
      </Text>
      <AdminConfig />
      <CredentialCard credKey="cred1" />
      <CredentialCard credKey="cred2" />
      <CredentialCard credKey="cred3" />
      <CredentialCard credKey="cred4" />
      <FreeTrialClaims />
      <ReferralSettings />
      <ReferralsSection />
      <SlotsSection />
      <TransactionsSection />
      <UIConfigSection />
      <UsedOrderIds />
      <UsersSection />
      <Spacer y={2} />
      <Text small css={{ textAlign: "center" }}>
        Dashboard built with NextUI and Firebase Realtime Database.
      </Text>
    </Container>
  );
};

const Home: React.FC = () => {
  return <Dashboard />;
};

export default Home;

import { useState, useEffect } from "react";
import { UIConfig, CrunchyrollScreen, NetflixPrimeScreen } from "@/types/database";
import { DataCard } from "@/components/ui/DataCard";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Edit, Save, Image, Plus, Trash } from "lucide-react";
import { updateData } from "@/lib/firebaseService";
import { updatePrimeData } from "@/lib/firebaseService";
import { updateNetflixData } from "@/lib/firebaseService";
import { toast } from "sonner";
import { useLocation } from "react-router-dom";

interface UIConfigPanelProps {
  uiConfig: UIConfig;
}

export function UIConfigPanel({ uiConfig }: UIConfigPanelProps) {
  const [activeSection, setActiveSection] = useState("start_command");
  const [editedConfig, setEditedConfig] = useState<UIConfig>({ ...uiConfig });
  const [isEditing, setIsEditing] = useState(false);
  const location = useLocation();

  const isNetflixOrPrime = location.pathname.includes("netflix") || location.pathname.includes("prime");

  // Update edited config when uiConfig prop changes
  useEffect(() => {
    setEditedConfig({ ...uiConfig });
  }, [uiConfig]);

  const getUpdateFunction = () => {
    if (location.pathname.includes("netflix")) {
      return updateNetflixData;
    } else if (location.pathname.includes("prime")) {
      return updatePrimeData;
    }
    return updateData; // Default for Crunchyroll
  };

  const handleSaveChanges = async () => {
    try {
      const updateFn = getUpdateFunction();
      await updateFn("/ui_config", editedConfig);
      toast.success("UI configuration updated successfully");
      setIsEditing(false);
    } catch (error) {
      console.error("Error updating UI config:", error);
      toast.error("Failed to update UI configuration");
    }
  };

  const handleInputChange = (section: string, field: string, value: any) => {
    setEditedConfig({
      ...editedConfig,
      [section]: {
        ...editedConfig[section as keyof UIConfig],
        [field]: value
      }
    });
  };

  const handleArrayChange = (section: string, field: string, index: number, value: any) => {
    const sectionData = editedConfig[section as keyof UIConfig] as any;
    const updatedArray = [...sectionData[field]];
    updatedArray[index] = value;
    
    setEditedConfig({
      ...editedConfig,
      [section]: {
        ...sectionData,
        [field]: updatedArray
      }
    });
  };

  const handleObjectArrayChange = (section: string, field: string, index: number, objField: string, value: any) => {
    const sectionData = editedConfig[section as keyof UIConfig] as any;
    const updatedArray = [...sectionData[field]];
    updatedArray[index] = {
      ...updatedArray[index],
      [objField]: value
    };
    
    setEditedConfig({
      ...editedConfig,
      [section]: {
        ...sectionData,
        [field]: updatedArray
      }
    });
  };

  const addButton = (section: string) => {
    const sectionData = editedConfig[section as keyof UIConfig] as any;
    const updatedButtons = [
      ...sectionData.buttons,
      { text: "New Button", callback_data: "new_button" }
    ];
    
    setEditedConfig({
      ...editedConfig,
      [section]: {
        ...sectionData,
        buttons: updatedButtons
      }
    });
  };

  const removeButton = (section: string, index: number) => {
    const sectionData = editedConfig[section as keyof UIConfig] as any;
    const updatedButtons = sectionData.buttons.filter((_: any, i: number) => i !== index);
    
    setEditedConfig({
      ...editedConfig,
      [section]: {
        ...sectionData,
        buttons: updatedButtons
      }
    });
  };

  const addMessage = (section: string) => {
    const sectionData = editedConfig[section as keyof UIConfig] as any;
    const updatedMessages = [
      ...sectionData.messages,
      "New message"
    ];
    
    setEditedConfig({
      ...editedConfig,
      [section]: {
        ...sectionData,
        messages: updatedMessages
      }
    });
  };

  const removeMessage = (section: string, index: number) => {
    const sectionData = editedConfig[section as keyof UIConfig] as any;
    const updatedMessages = sectionData.messages.filter((_: any, i: number) => i !== index);
    
    setEditedConfig({
      ...editedConfig,
      [section]: {
        ...sectionData,
        messages: updatedMessages
      }
    });
  };

  // Function to get the correct media URL based on service type
  const getMediaUrl = (screen: CrunchyrollScreen | NetflixPrimeScreen): string => {
    if (isNetflixOrPrime) {
      return (screen as NetflixPrimeScreen).gif_url || "";
    } else {
      return (screen as CrunchyrollScreen).photo_url || "";
    }
  };

  // This key helps force re-render of images when URLs change
  const [imageKey, setImageKey] = useState(Date.now());
  
  // Force re-render of images when edited config changes
  useEffect(() => {
    setImageKey(Date.now());
  }, [editedConfig]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">UI Configuration</h2>
        <Button
          variant={isEditing ? "default" : "outline"}
          onClick={() => {
            if (isEditing) {
              setEditedConfig({ ...uiConfig });
            }
            setIsEditing(!isEditing);
          }}
        >
          {isEditing ? "Cancel" : <><Edit className="mr-2 h-4 w-4" /> Edit</>}
        </Button>
      </div>

      <Tabs value={activeSection} onValueChange={setActiveSection} className="w-full">
        <TabsList className="w-full mb-6 grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 h-auto p-1 glass-morphism">
          <TabsTrigger value="start_command">Start</TabsTrigger>
          <TabsTrigger value="crunchyroll_screen">Crunchyroll</TabsTrigger>
          <TabsTrigger value="slot_booking">Slot Booking</TabsTrigger>
          <TabsTrigger value="confirmation_flow">Confirmation</TabsTrigger>
          <TabsTrigger value="phonepe_screen">PhonePe</TabsTrigger>
          <TabsTrigger value="approve_flow">Approve</TabsTrigger>
          <TabsTrigger value="posters">Posters</TabsTrigger>
          <TabsTrigger value="other">Other</TabsTrigger>
        </TabsList>
        
        <TabsContent value="start_command" className="mt-0">
          <DataCard title="Start Command Configuration">
            <div className="space-y-6">
              {isEditing ? (
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="welcome-text">Welcome Text</Label>
                    <Textarea
                      id="welcome-text"
                      value={editedConfig.start_command.welcome_text}
                      onChange={(e) => handleInputChange('start_command', 'welcome_text', e.target.value)}
                      rows={3}
                    />
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="welcome-photo">Welcome Photo URL</Label>
                    <Input
                      id="welcome-photo"
                      value={editedConfig.start_command.welcome_photo}
                      onChange={(e) => handleInputChange('start_command', 'welcome_photo', e.target.value)}
                    />
                  </div>
                  
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label>Buttons</Label>
                      <Button size="sm" variant="outline" onClick={() => addButton('start_command')}>
                        <Plus className="h-4 w-4 mr-1" /> Add Button
                      </Button>
                    </div>
                    
                    <div className="space-y-3">
                      {editedConfig.start_command.buttons.map((button, index) => (
                        <div key={index} className="grid grid-cols-3 gap-2 items-start">
                          <div className="col-span-1">
                            <Input
                              value={button.text}
                              onChange={(e) => handleObjectArrayChange('start_command', 'buttons', index, 'text', e.target.value)}
                              placeholder="Button Text"
                            />
                          </div>
                          <div className="col-span-1">
                            <Input
                              value={button.callback_data}
                              onChange={(e) => handleObjectArrayChange('start_command', 'buttons', index, 'callback_data', e.target.value)}
                              placeholder="Callback Data"
                            />
                          </div>
                          <Button 
                            variant="destructive" 
                            size="sm"
                            onClick={() => removeButton('start_command', index)}
                            className="col-span-1 h-10"
                          >
                            <Trash className="h-4 w-4" />
                          </Button>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="glass-morphism p-4 rounded-md">
                    <h3 className="text-sm font-medium mb-2 text-muted-foreground">Welcome Text</h3>
                    <p className="whitespace-pre-line">{editedConfig.start_command.welcome_text}</p>
                  </div>
                  
                  <div>
                    <h3 className="text-sm font-medium mb-2 text-muted-foreground">Welcome Photo</h3>
                    <div className="glass-morphism p-2 rounded-md overflow-hidden">
                      <div className="relative aspect-video bg-black/20 rounded overflow-hidden">
                        <img 
                          key={`welcome-photo-${imageKey}`}
                          src={editedConfig.start_command.welcome_photo}
                          alt="Welcome"
                          className="absolute inset-0 w-full h-full object-cover object-center"
                          onError={(e) => {
                            (e.target as HTMLImageElement).src = 'https://placehold.co/400x225?text=Image+Not+Found';
                          }}
                        />
                      </div>
                    </div>
                  </div>
                  
                  <div>
                    <h3 className="text-sm font-medium mb-2 text-muted-foreground">Buttons</h3>
                    <div className="flex flex-wrap gap-2">
                      {editedConfig.start_command.buttons.map((button, index) => (
                        <div key={index} className="glass-morphism p-2 rounded-md">
                          <div className="font-medium">{button.text}</div>
                          <div className="text-xs text-muted-foreground">{button.callback_data}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </DataCard>
        </TabsContent>
        
        <TabsContent value="crunchyroll_screen" className="mt-0">
          <DataCard title="Crunchyroll Screen Configuration">
            <div className="space-y-6">
              {isEditing ? (
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="cr-caption">Caption</Label>
                    <Textarea
                      id="cr-caption"
                      value={editedConfig.crunchyroll_screen.caption}
                      onChange={(e) => handleInputChange('crunchyroll_screen', 'caption', e.target.value)}
                      rows={3}
                    />
                  </div>
                  
                  <div className="space-y-2">
                    {isNetflixOrPrime ? (
                      <>
                        <Label htmlFor="cr-gif">GIF URL</Label>
                        <Input
                          id="cr-gif"
                          value={(editedConfig.crunchyroll_screen as NetflixPrimeScreen).gif_url || ""}
                          onChange={(e) => handleInputChange('crunchyroll_screen', 'gif_url', e.target.value)}
                        />
                      </>
                    ) : (
                      <>
                        <Label htmlFor="cr-photo">Photo URL</Label>
                        <Input
                          id="cr-photo"
                          value={(editedConfig.crunchyroll_screen as CrunchyrollScreen).photo_url || ""}
                          onChange={(e) => handleInputChange('crunchyroll_screen', 'photo_url', e.target.value)}
                        />
                      </>
                    )}
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="cr-button-text">Button Text</Label>
                      <Input
                        id="cr-button-text"
                        value={editedConfig.crunchyroll_screen.button_text}
                        onChange={(e) => handleInputChange('crunchyroll_screen', 'button_text', e.target.value)}
                      />
                    </div>
                    
                    <div className="space-y-2">
                      <Label htmlFor="cr-callback">Callback Data</Label>
                      <Input
                        id="cr-callback"
                        value={editedConfig.crunchyroll_screen.callback_data}
                        onChange={(e) => handleInputChange('crunchyroll_screen', 'callback_data', e.target.value)}
                      />
                    </div>
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="glass-morphism p-4 rounded-md">
                    <h3 className="text-sm font-medium mb-2 text-muted-foreground">Caption</h3>
                    <p className="whitespace-pre-line">{editedConfig.crunchyroll_screen.caption}</p>
                  </div>
                  
                  <div>
                    <h3 className="text-sm font-medium mb-2 text-muted-foreground">
                      {isNetflixOrPrime ? "GIF" : "Photo"}
                    </h3>
                    <div className="glass-morphism p-2 rounded-md overflow-hidden">
                      <div className="relative aspect-video bg-black/20 rounded overflow-hidden">
                        <img 
                          key={`crunchyroll-media-${imageKey}`}
                          src={getMediaUrl(editedConfig.crunchyroll_screen)}
                          alt="Crunchyroll Screen"
                          className="absolute inset-0 w-full h-full object-cover object-center"
                          onError={(e) => {
                            (e.target as HTMLImageElement).src = 'https://placehold.co/400x225?text=Image+Not+Found';
                          }}
                        />
                      </div>
                    </div>
                  </div>
                  
                  <div className="glass-morphism p-4 rounded-md">
                    <h3 className="text-sm font-medium mb-2 text-muted-foreground">Button</h3>
                    <div className="flex justify-between">
                      <div>{editedConfig.crunchyroll_screen.button_text}</div>
                      <div className="text-sm text-muted-foreground">{editedConfig.crunchyroll_screen.callback_data}</div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </DataCard>
        </TabsContent>
        
        <TabsContent value="slot_booking" className="mt-0">
          <DataCard title="Slot Booking Configuration">
            <div className="space-y-6">
              {isEditing ? (
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="slot-caption">Caption</Label>
                    <Textarea
                      id="slot-caption"
                      value={editedConfig.slot_booking.caption}
                      onChange={(e) => handleInputChange('slot_booking', 'caption', e.target.value)}
                      rows={3}
                    />
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="slot-photo">Photo URL</Label>
                      <Input
                        id="slot-photo"
                        value={editedConfig.slot_booking.photo_url}
                        onChange={(e) => handleInputChange('slot_booking', 'photo_url', e.target.value)}
                      />
                    </div>
                    
                    <div className="space-y-2">
                      <Label htmlFor="slot-gif">GIF URL</Label>
                      <Input
                        id="slot-gif"
                        value={editedConfig.slot_booking.gif_url}
                        onChange={(e) => handleInputChange('slot_booking', 'gif_url', e.target.value)}
                      />
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="slot-format">Button Format</Label>
                      <Input
                        id="slot-format"
                        value={editedConfig.slot_booking.button_format}
                        onChange={(e) => handleInputChange('slot_booking', 'button_format', e.target.value)}
                      />
                    </div>
                    
                    <div className="space-y-2">
                      <Label htmlFor="slot-callback">Callback Data</Label>
                      <Input
                        id="slot-callback"
                        value={editedConfig.slot_booking.callback_data}
                        onChange={(e) => handleInputChange('slot_booking', 'callback_data', e.target.value)}
                      />
                    </div>
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="glass-morphism p-4 rounded-md">
                    <h3 className="text-sm font-medium mb-2 text-muted-foreground">Caption</h3>
                    <p className="whitespace-pre-line">{editedConfig.slot_booking.caption}</p>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <h3 className="text-sm font-medium mb-2 text-muted-foreground">Photo</h3>
                      <div className="glass-morphism p-2 rounded-md overflow-hidden">
                        <div className="relative aspect-square bg-black/20 rounded overflow-hidden">
                          <img 
                            src={editedConfig.slot_booking.photo_url}
                            alt="Slot Booking"
                            className="absolute inset-0 w-full h-full object-cover object-center"
                            onError={(e) => {
                              (e.target as HTMLImageElement).src = 'https://placehold.co/300x300?text=Image+Not+Found';
                            }}
                          />
                        </div>
                      </div>
                    </div>
                    
                    <div>
                      <h3 className="text-sm font-medium mb-2 text-muted-foreground">GIF</h3>
                      <div className="glass-morphism p-2 rounded-md overflow-hidden">
                        <div className="relative aspect-square bg-black/20 rounded overflow-hidden">
                          <img 
                            src={editedConfig.slot_booking.gif_url}
                            alt="Slot Booking GIF"
                            className="absolute inset-0 w-full h-full object-cover object-center"
                            onError={(e) => {
                              (e.target as HTMLImageElement).src = 'https://placehold.co/300x300?text=GIF+Not+Found';
                            }}
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                  
                  <div className="glass-morphism p-4 rounded-md">
                    <h3 className="text-sm font-medium mb-2 text-muted-foreground">Button Configuration</h3>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <span className="text-sm text-muted-foreground">Format:</span>
                        <p>{editedConfig.slot_booking.button_format}</p>
                      </div>
                      <div>
                        <span className="text-sm text-muted-foreground">Callback:</span>
                        <p>{editedConfig.slot_booking.callback_data}</p>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </DataCard>
        </TabsContent>
        
        <TabsContent value="confirmation_flow" className="mt-0">
          <DataCard title="Confirmation Flow Configuration">
            <div className="space-y-6">
              {isEditing ? (
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="confirmation-caption">Caption</Label>
                    <Textarea
                      id="confirmation-caption"
                      value={editedConfig.confirmation_flow.caption}
                      onChange={(e) => handleInputChange('confirmation_flow', 'caption', e.target.value)}
                      rows={3}
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="confirmation-photo">Photo URL</Label>
                      <Input
                        id="confirmation-photo"
                        value={editedConfig.confirmation_flow.photo_url}
                        onChange={(e) => handleInputChange('confirmation_flow', 'photo_url', e.target.value)}
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="confirmation-gif">GIF URL</Label>
                      <Input
                        id="confirmation-gif"
                        value={editedConfig.confirmation_flow.gif_url}
                        onChange={(e) => handleInputChange('confirmation_flow', 'gif_url', e.target.value)}
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="confirmation-button-text">Button Text</Label>
                      <Input
                        id="confirmation-button-text"
                        value={editedConfig.confirmation_flow.button_text}
                        onChange={(e) => handleInputChange('confirmation_flow', 'button_text', e.target.value)}
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="confirmation-callback">Callback Data</Label>
                      <Input
                        id="confirmation-callback"
                        value={editedConfig.confirmation_flow.callback_data}
                        onChange={(e) => handleInputChange('confirmation_flow', 'callback_data', e.target.value)}
                      />
                    </div>
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="glass-morphism p-4 rounded-md">
                    <h3 className="text-sm font-medium mb-2 text-muted-foreground">Caption</h3>
                    <p className="whitespace-pre-line">{editedConfig.confirmation_flow.caption}</p>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <h3 className="text-sm font-medium mb-2 text-muted-foreground">Photo</h3>
                      <div className="glass-morphism p-2 rounded-md overflow-hidden">
                        <div className="relative aspect-square bg-black/20 rounded overflow-hidden">
                          <img
                            src={editedConfig.confirmation_flow.photo_url}
                            alt="Confirmation Photo"
                            className="absolute inset-0 w-full h-full object-cover object-center"
                            onError={(e) => {
                              (e.target as HTMLImageElement).src = 'https://placehold.co/300x300?text=Image+Not+Found';
                            }}
                          />
                        </div>
                      </div>
                    </div>

                    <div>
                      <h3 className="text-sm font-medium mb-2 text-muted-foreground">GIF</h3>
                      <div className="glass-morphism p-2 rounded-md overflow-hidden">
                        <div className="relative aspect-square bg-black/20 rounded overflow-hidden">
                          <img
                            src={editedConfig.confirmation_flow.gif_url}
                            alt="Confirmation GIF"
                            className="absolute inset-0 w-full h-full object-cover object-center"
                            onError={(e) => {
                              (e.target as HTMLImageElement).src = 'https://placehold.co/300x300?text=GIF+Not+Found';
                            }}
                          />
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="glass-morphism p-4 rounded-md">
                    <h3 className="text-sm font-medium mb-2 text-muted-foreground">Button Configuration</h3>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <span className="text-sm text-muted-foreground">Text:</span>
                        <p>{editedConfig.confirmation_flow.button_text}</p>
                      </div>
                      <div>
                        <span className="text-sm text-muted-foreground">Callback:</span>
                        <p>{editedConfig.confirmation_flow.callback_data}</p>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </DataCard>
        </TabsContent>

        <TabsContent value="phonepe_screen" className="mt-0">
          <DataCard title="PhonePe Screen Configuration">
            <div className="space-y-6">
              {isEditing ? (
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="phonepe-caption">Caption</Label>
                    <Textarea
                      id="phonepe-caption"
                      value={editedConfig.phonepe_screen.caption}
                      onChange={(e) => handleInputChange('phonepe_screen', 'caption', e.target.value)}
                      rows={3}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="phonepe-followup">Follow-up Text</Label>
                    <Textarea
                      id="phonepe-followup"
                      value={editedConfig.phonepe_screen.followup_text}
                      onChange={(e) => handleInputChange('phonepe_screen', 'followup_text', e.target.value)}
                      rows={3}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="phonepe-photo">Photo URL</Label>
                    <Input
                      id="phonepe-photo"
                      value={editedConfig.phonepe_screen.photo_url}
                      onChange={(e) => handleInputChange('phonepe_screen', 'photo_url', e.target.value)}
                    />
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="glass-morphism p-4 rounded-md">
                    <h3 className="text-sm font-medium mb-2 text-muted-foreground">Caption</h3>
                    <p className="whitespace-pre-line">{editedConfig.phonepe_screen.caption}</p>
                  </div>

                  <div className="glass-morphism p-4 rounded-md">
                    <h3 className="text-sm font-medium mb-2 text-muted-foreground">Follow-up Text</h3>
                    <p className="whitespace-pre-line">{editedConfig.phonepe_screen.followup_text}</p>
                  </div>

                  <div>
                    <h3 className="text-sm font-medium mb-2 text-muted-foreground">Photo</h3>
                    <div className="glass-morphism p-2 rounded-md overflow-hidden">
                      <div className="relative aspect-video bg-black/20 rounded overflow-hidden">
                        <img
                          src={editedConfig.phonepe_screen.photo_url}
                          alt="PhonePe Screen"
                          className="absolute inset-0 w-full h-full object-cover object-center"
                          onError={(e) => {
                            (e.target as HTMLImageElement).src = 'https://placehold.co/400x225?text=Image+Not+Found';
                          }}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </DataCard>
        </TabsContent>

        <TabsContent value="approve_flow" className="mt-0">
          <DataCard title="Approve Flow Configuration">
            <div className="space-y-6">
              {isEditing ? (
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="approve-success-text">Success Text</Label>
                    <Textarea
                      id="approve-success-text"
                      value={editedConfig.approve_flow.success_text}
                      onChange={(e) => handleInputChange('approve_flow', 'success_text', e.target.value)}
                      rows={3}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="approve-account-format">Account Format</Label>
                    <Textarea
                      id="approve-account-format"
                      value={editedConfig.approve_flow.account_format}
                      onChange={(e) => handleInputChange('approve_flow', 'account_format', e.target.value)}
                      rows={3}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="approve-gif">GIF URL</Label>
                    <Input
                      id="approve-gif"
                      value={editedConfig.approve_flow.gif_url}
                      onChange={(e) => handleInputChange('approve_flow', 'gif_url', e.target.value)}
                    />
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="glass-morphism p-4 rounded-md">
                    <h3 className="text-sm font-medium mb-2 text-muted-foreground">Success Text</h3>
                    <p className="whitespace-pre-line">{editedConfig.approve_flow.success_text}</p>
                  </div>

                  <div className="glass-morphism p-4 rounded-md">
                    <h3 className="text-sm font-medium mb-2 text-muted-foreground">Account Format</h3>
                    <p className="whitespace-pre-line">{editedConfig.approve_flow.account_format}</p>
                  </div>

                  <div>
                    <h3 className="text-sm font-medium mb-2 text-muted-foreground">GIF</h3>
                    <div className="glass-morphism p-2 rounded-md overflow-hidden">
                      <div className="relative aspect-video bg-black/20 rounded overflow-hidden">
                        <img
                          src={editedConfig.approve_flow.gif_url}
                          alt="Approve Flow GIF"
                          className="absolute inset-0 w-full h-full object-cover object-center"
                          onError={(e) => {
                            (e.target as HTMLImageElement).src = 'https://placehold.co/400x225?text=GIF+Not+Found';
                          }}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </DataCard>
        </TabsContent>
        
        <TabsContent value="posters" className="mt-0">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <DataCard title="Referral Info">
              <div className="space-y-4">
                {isEditing ? (
                  <div className="space-y-2">
                    <Label htmlFor="referral-photo">Referral Photo URL</Label>
                    <Input
                      id="referral-photo"
                      value={editedConfig.referral_info.photo_url}
                      onChange={(e) => handleInputChange('referral_info', 'photo_url', e.target.value)}
                    />
                  </div>
                ) : (
                  <div>
                    <h3 className="text-sm font-medium mb-2 text-muted-foreground">Referral Photo</h3>
                    <div className="glass-morphism p-2 rounded-md overflow-hidden">
                      <div className="relative aspect-video bg-black/20 rounded overflow-hidden">
                        <img 
                          src={editedConfig.referral_info.photo_url}
                          alt="Referral Information"
                          className="absolute inset-0 w-full h-full object-cover object-center"
                          onError={(e) => {
                            (e.target as HTMLImageElement).src = 'https://placehold.co/400x225?text=Image+Not+Found';
                          }}
                        />
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </DataCard>
            
            <DataCard title="Free Trial Info">
              <div className="space-y-4">
                {isEditing ? (
                  <div className="space-y-2">
                    <Label htmlFor="freetrial-photo">Free Trial Photo URL</Label>
                    <Input
                      id="freetrial-photo"
                      value={editedConfig.freetrial_info.photo_url}
                      onChange={(e) => handleInputChange('freetrial_info', 'photo_url', e.target.value)}
                    />
                  </div>
                ) : (
                  <div>
                    <h3 className="text-sm font-medium mb-2 text-muted-foreground">Free Trial Photo</h3>
                    <div className="glass-morphism p-2 rounded-md overflow-hidden">
                      <div className="relative aspect-video bg-black/20 rounded overflow-hidden">
                        <img 
                          src={editedConfig.freetrial_info.photo_url}
                          alt="Free Trial Information"
                          className="absolute inset-0 w-full h-full object-cover object-center"
                          onError={(e) => {
                            (e.target as HTMLImageElement).src = 'https://placehold.co/400x225?text=Image+Not+Found';
                          }}
                        />
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </DataCard>
          </div>
        </TabsContent>
        
        <TabsContent value="other" className="mt-0">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <DataCard title="Out of Stock Messages">
              <div className="space-y-4">
                {isEditing ? (
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="stock-gif">GIF URL</Label>
                      <Input
                        id="stock-gif"
                        value={editedConfig.out_of_stock.gif_url}
                        onChange={(e) => handleInputChange('out_of_stock', 'gif_url', e.target.value)}
                      />
                    </div>
                    
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <Label>Messages</Label>
                        <Button size="sm" variant="outline" onClick={() => addMessage('out_of_stock')}>
                          <Plus className="h-4 w-4 mr-1" /> Add Message
                        </Button>
                      </div>
                      
                      <div className="space-y-2">
                        {editedConfig.out_of_stock.messages.map((message, index) => (
                          <div key={index} className="flex gap-2">
                            <Textarea
                              value={message}
                              onChange={(e) => handleArrayChange('out_of_stock', 'messages', index, e.target.value)}
                              className="flex-1"
                            />
                            <Button 
                              variant="destructive" 
                              size="sm"
                              onClick={() => removeMessage('out_of_stock', index)}
                              className="h-10"
                            >
                              <Trash className="h-4 w-4" />
                            </Button>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div>
                      <h3 className="text-sm font-medium mb-2 text-muted-foreground">GIF</h3>
                      <div className="glass-morphism p-2 rounded-md overflow-hidden">
                        <div className="relative aspect-video bg-black/20 rounded overflow-hidden">
                          <img 
                            src={editedConfig.out_of_stock.gif_url}
                            alt="Out of Stock GIF"
                            className="absolute inset-0 w-full h-full object-cover object-center"
                            onError={(e) => {
                              (e.target as HTMLImageElement).src = 'https://placehold.co/400x225?text=GIF+Not+Found';
                            }}
                          />
                        </div>
                      </div>
                    </div>
                    
                    <div>
                      <h3 className="text-sm font-medium mb-2 text-muted-foreground">Messages</h3>
                      <div className="space-y-2">
                        {editedConfig.out_of_stock.messages.map((message, index) => (
                          <div key={index} className="glass-morphism p-3 rounded-md">
                            <p className="whitespace-pre-line">{message}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </DataCard>
            
            <DataCard title="Locked Flow">
              <div className="space-y-4">
                {isEditing ? (
                  <div className="space-y-2">
                    <Label htmlFor="locked-text">Locked Text</Label>
                    <Textarea
                      id="locked-text"
                      value={editedConfig.locked_flow.locked_text}
                      onChange={(e) => handleInputChange('locked_flow', 'locked_text', e.target.value)}
                      rows={5}
                    />
                  </div>
                ) : (
                  <div className="glass-morphism p-4 rounded-md">
                    <h3 className="text-sm font-medium mb-2 text-muted-foreground">Locked Text</h3>
                    <p className="whitespace-pre-line">{editedConfig.locked_flow.locked_text}</p>
                  </div>
                )}
              </div>
            </DataCard>
          </div>
        </TabsContent>
        
        {/* Add more TabsContent sections for other UI config elements */}
        
      </Tabs>
      
      {isEditing && (
        <div className="flex justify-end mt-4">
          <Button onClick={handleSaveChanges}>
            <Save className="mr-2 h-4 w-4" /> Save Changes
          </Button>
        </div>
      )}
    </div>
  );
}

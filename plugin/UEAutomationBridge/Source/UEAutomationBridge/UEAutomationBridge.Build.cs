using UnrealBuildTool;

public class UEAutomationBridge : ModuleRules
{
    public UEAutomationBridge(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.AddRange(new string[]
        {
            "Core",
        });

        PrivateDependencyModuleNames.AddRange(new string[]
        {
            "CoreUObject",
            "Engine",
            "UnrealEd",
            "Json",
            "JsonUtilities",
        });
    }
}

#include "Commandlets/StateTreeSnapshotCommandlet.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

UStateTreeSnapshotCommandlet::UStateTreeSnapshotCommandlet()
{
    IsClient = false;
    IsServer = false;
    IsEditor = true;
    LogToConsole = true;
}

FString UStateTreeSnapshotCommandlet::ParseAssetPath(const FString& Params) const
{
    FString AssetPath;
    FParse::Value(*Params, TEXT("asset="), AssetPath);
    return AssetPath;
}

FString UStateTreeSnapshotCommandlet::ParseOutPath(const FString& Params) const
{
    FString OutPath;
    if (!FParse::Value(*Params, TEXT("out="), OutPath))
    {
        OutPath = FPaths::ProjectSavedDir() / TEXT("AutomationReports/statetree.snapshot.json");
    }
    return OutPath;
}

int32 UStateTreeSnapshotCommandlet::Main(const FString& Params)
{
    FString AssetPath = ParseAssetPath(Params);
    if (AssetPath.IsEmpty())
    {
        UE_LOG(LogTemp, Error, TEXT("StateTreeSnapshot: -asset= is required"));
        return 1;
    }

    // Extract the asset name from the last path segment (e.g. /Game/AI/ST_Enemy → ST_Enemy)
    FString AssetName = FPaths::GetBaseFilename(AssetPath);
    if (AssetName.IsEmpty())
    {
        AssetName = AssetPath;
    }

    FString OutPath = ParseOutPath(Params);

    // Stub: emits a single Root state. Full StateTree node introspection is deferred to Sprint 4+.
    TSharedPtr<FJsonObject> RootState = MakeShared<FJsonObject>();
    RootState->SetStringField(TEXT("name"), TEXT("Root"));
    RootState->SetField(TEXT("parent"), MakeShared<FJsonValueNull>());
    RootState->SetArrayField(TEXT("tasks"), TArray<TSharedPtr<FJsonValue>>{});
    RootState->SetArrayField(TEXT("transitions"), TArray<TSharedPtr<FJsonValue>>{});

    TArray<TSharedPtr<FJsonValue>> States;
    States.Add(MakeShared<FJsonValueObject>(RootState));

    TSharedRef<FJsonObject> Snapshot = MakeShared<FJsonObject>();
    Snapshot->SetStringField(TEXT("asset_path"), AssetPath);
    Snapshot->SetStringField(TEXT("name"), AssetName);
    Snapshot->SetArrayField(TEXT("states"), States);

    FString JsonString;
    TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&JsonString);
    if (!FJsonSerializer::Serialize(Snapshot, Writer))
    {
        UE_LOG(LogTemp, Error, TEXT("StateTreeSnapshot: JSON serialization failed"));
        return 1;
    }

    IPlatformFile& PF = FPlatformFileManager::Get().GetPlatformFile();
    if (!PF.CreateDirectoryTree(*FPaths::GetPath(OutPath)))
    {
        UE_LOG(LogTemp, Error, TEXT("StateTreeSnapshot: failed to create output directory: %s"), *FPaths::GetPath(OutPath));
        return 1;
    }
    if (!FFileHelper::SaveStringToFile(JsonString, *OutPath))
    {
        UE_LOG(LogTemp, Error, TEXT("StateTreeSnapshot: failed to write output file: %s"), *OutPath);
        return 1;
    }

    UE_LOG(LogTemp, Display,
        TEXT("StateTreeSnapshot: wrote snapshot for '%s' to %s"), *AssetName, *OutPath);
    return 0;
}

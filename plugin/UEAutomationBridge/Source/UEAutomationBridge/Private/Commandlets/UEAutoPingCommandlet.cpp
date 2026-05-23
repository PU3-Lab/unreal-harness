#include "Commandlets/UEAutoPingCommandlet.h"
#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

UUEAutoPingCommandlet::UUEAutoPingCommandlet()
{
    IsClient = false;
    IsServer = false;
    IsEditor = true;
    LogToConsole = true;
}

int32 UUEAutoPingCommandlet::Main(const FString& Params)
{
    TSharedRef<FJsonObject> Result = MakeShared<FJsonObject>();
    Result->SetBoolField(TEXT("ok"), true);
    Result->SetStringField(TEXT("action"), TEXT("ping"));
    Result->SetStringField(TEXT("message"), TEXT("pong"));
    Result->SetStringField(TEXT("timestamp"), FDateTime::UtcNow().ToIso8601());

    FString OutputPath = FPaths::ProjectSavedDir() / TEXT("AutomationReports/result.json");
    IPlatformFile& PF = FPlatformFileManager::Get().GetPlatformFile();
    PF.CreateDirectoryTree(*FPaths::GetPath(OutputPath));

    FString JsonString;
    TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&JsonString);
    FJsonSerializer::Serialize(Result, Writer);
    FFileHelper::SaveStringToFile(JsonString, *OutputPath);

    UE_LOG(LogTemp, Display, TEXT("UEAuto ping: pong — result written to %s"), *OutputPath);
    return 0;
}
